"""分配结果业务服务

包含：
- AdmissionService：录取结果查询 + 统一的「锁定座位不变量」写入入口
- AutoAssignmentLogService：自动分配日志查询（只读）
- AutoAssignmentService：自动分配算法（DATABASE.md 7.7 / 7.8）

自动分配算法依据 DATABASE.md 7.7：
1. 获取分布式锁 lock:auto_assign:{academic_year_id}
2. 校验 system_state = AUTO_ASSIGN
3. 校验当前无运行中自动分配任务
4. 查询未分配学生列表（当前学年无 admission）
5. 查询有剩余名额的导师列表（按剩余名额降序 + teacher_number 升序）
6. 创建 auto_assignment_log (status=RUNNING)
7. 对每个未分配学生（独立事务）：
   a. 锁学生行 -> SELECT teacher_quota ... FOR UPDATE
   b. 校验 remaining_quota > 0（当前读计数）
   c. 创建 admission (source=AUTO_ASSIGNED)
   d. 写入 operation_log
   失败 → 重试该条，3 次失败跳过并记 failed_count++
8. 更新 auto_assignment_log (status=SUCCESS/PARTIAL/FAILED)
9. 若全部学生已分配（failed_count=0）：状态转换 AUTO_ASSIGN → FINISHED
10. 释放分布式锁

一致性原则：
- Redis 分布式锁只是**辅助**（降低并发冲突概率），不作为正确性依据；
  座位是否可分配一律以 DB 行锁 + 当前读计数为准。
- MySQL REPEATABLE READ 下，事务早期普通 SELECT 建立的快照会让后续普通
  SELECT 读到过期计数；因此所有名额判定都使用 select_for_update 物化的「当前读」。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.assignments.models import Admission, AutoAssignmentLog
from apps.assignments.repositories import (
    AdmissionRepository,
    AutoAssignmentLogRepository,
)
from apps.assignments.serializers import ManualAssignRequestSerializer  # noqa: F401
from apps.common.cache_keys import lock_auto_assign, LOCK_TTL_AUTO_ASSIGN
from apps.common.enums import (
    AdmissionSource,
    AutoAssignmentStatus,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    StateTransitionError,
)
from apps.common.logger import get_logger, log_business_event
from apps.common.lock import DistributedLock, LockAcquisitionError
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService
from apps.students.models import StudentProfile
from apps.students.repositories import StudentProfileRepository
from apps.system.repositories import SystemStateRepository
from apps.system.services import SystemStateService
from apps.teachers.repositories import TeacherProfileRepository, TeacherQuotaRepository

logger = get_logger("assignments.services")


class AdmissionService(BaseService):
    """录取结果业务服务

    录取结果由业务流程产生（申请通过 / 人工分配 / 自动分配），
    不通过 API 直接创建/修改/删除。
    跨聚合写入由本服务统一封装，避免其他 Service 直接操作 assignments.models。
    """

    repository = AdmissionRepository()
    _quota_repo = TeacherQuotaRepository()
    _system_state_repo = SystemStateRepository()
    # 参与方档案查询（service 只组合 Repository，不直接写 ORM 查询）
    _student_repo = StudentProfileRepository()
    _teacher_repo = TeacherProfileRepository()

    # ===== 查询 =====

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询录取结果列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> Admission:
        return self.repository.get_by_id(pk)

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询录取结果"""
        return self.repository.list_by_academic_year(academic_year_id)

    def list_by_teacher(self, teacher_id: int, academic_year_id: int | None = None):
        """按导师查询录取结果"""
        return self.repository.list_by_teacher(teacher_id, academic_year_id)

    def list_by_student(self, student_id: int):
        """按学生查询录取结果"""
        return self.repository.list_by_student(student_id)

    def get_by_year_student(
        self, academic_year_id: int, student_id: int
    ) -> Admission | None:
        """按学年+学生查询录取结果"""
        return self.repository.get_by_year_student(academic_year_id, student_id)

    def count_by_teacher(self, teacher_id: int, academic_year_id: int) -> int:
        """统计导师在某学年的已录取人数（普通快照读，仅用于展示/统计）"""
        return self.repository.count_by_teacher(teacher_id, academic_year_id)

    # ===== 统一种子：锁定座位不变量 =====

    @transaction.atomic
    def lock_student(self, student_id: int):
        """锁定学生行（固定锁顺序第 1 步）

        串行化「同一学生」的占用判定，避免同一学生并发产生两条录取记录
        （例如同时提交第二轮申请与人工分配）。

        必须在 transaction.atomic 内调用；锁持有至事务提交。
        """
        return self.repository.lock_student_row(student_id)

    @transaction.atomic
    def lock_seat_invariant(
        self,
        academic_year_id: int,
        teacher_id: int,
        student_id: int | None = None,
    ) -> "SeatContext":
        """加锁并计算「座位不变量」——所有分配路径的唯一入口

        固定锁顺序（全项目统一，防死锁）：
          1. student 行锁（select_for_update）
          2. teacher_quota 行锁（select_for_update）
          3. admission **当前读**计数（select_for_update 物化）

        第 3 步必须为当前读：在 MySQL REPEATABLE READ 下，事务内先执行过
        普通 SELECT 后再普通 SELECT 会复用旧快照，即使持有 quota 行锁，
        仍可能读到过期计数而放行超额录取。

        必须在 transaction.atomic 内调用。
        """
        student = None
        if student_id is not None:
            student = self.repository.lock_student_row(student_id)

        quota = self._quota_repo.get_for_update_by_year_and_teacher(
            academic_year_id, teacher_id
        )
        admitted_count = self.repository.count_by_teacher_current(
            teacher_id, academic_year_id
        )

        max_quota = quota.max_quota if quota is not None else None
        remaining = (max_quota - admitted_count) if max_quota is not None else None

        return SeatContext(
            academic_year_id=academic_year_id,
            teacher_id=teacher_id,
            student_id=student_id,
            student=student,
            quota=quota,
            max_quota=max_quota,
            admitted_count=admitted_count,
            remaining_quota=remaining,
        )

    def assert_seat_available(self, ctx: "SeatContext") -> None:
        """校验座位可分配（未配置名额 = 已关闭，绝不视为无限）

        Raises:
            BusinessException: 未配置名额 / 名额已满
        """
        if ctx.quota is None:
            raise BusinessException(
                "该导师在本学年未配置招生名额，当前不可录取",
                code=ErrorCode.QUOTA_NOT_FOUND,
            )
        if ctx.remaining_quota is not None and ctx.remaining_quota <= 0:
            raise BusinessException(
                "该导师名额已满，无法录取",
                code=ErrorCode.ADMISSION_QUOTA_FULL,
            )

    @staticmethod
    def _assert_user_can_participate(user, label: str) -> None:
        """校验账号可参与分配（存在 / 未删除 / 启用）"""
        if user is None:
            raise BusinessException(
                f"{label}账号不存在，无法参与分配",
                code=ErrorCode.NOT_FOUND,
            )
        if getattr(user, "deleted_at", None) is not None:
            raise BusinessException(
                f"{label}账号已删除，无法参与分配",
                code=ErrorCode.PERMISSION_DENIED,
            )
        if (
            not getattr(user, "is_active", True)
            or getattr(user, "status", UserStatus.ACTIVE.value)
            != UserStatus.ACTIVE.value
        ):
            raise BusinessException(
                f"{label}账号已被禁用，无法参与分配",
                code=ErrorCode.PERMISSION_DENIED,
            )

    # ===== 写入（统一入口） =====

    @transaction.atomic
    def allocate(
        self,
        academic_year_id: int,
        student_id: int,
        teacher_id: int,
        source: int,
        application=None,
        auto_assignment_log_id: int | None = None,
    ) -> Admission:
        """统一分配入口：所有录取写入都必须经过这里

        步骤（同一事务、同一锁协议）：
        1. 锁学生行 + 锁名额行 + admission 当前读计数
        2. 名额不变量判定（未配置名额 / 已满 → 拒绝）
        3. 学生本学年唯一性校验（加锁读；DB 唯一约束 uk_year_student 兜底）
        4. 参与方（学生/导师）必须存在且启用
        5. 创建 admission
        """
        ctx = self.lock_seat_invariant(academic_year_id, teacher_id, student_id)
        self.assert_seat_available(ctx)

        # 学生本学年唯一性（加行锁读取，配合 uk_year_student 唯一约束）
        existing = self.repository.get_by_year_student_for_update(
            academic_year_id, student_id
        )
        if existing is not None:
            raise BusinessException(
                "该学生本学年已有录取记录",
                code=ErrorCode.ADMISSION_EXISTS,
            )

        # 参与方校验：禁用的学生/导师不得参与分配
        # 查询一律委托 Repository（select_related("user")），Service 不再直接写 ORM
        student = ctx.student or self._student_repo.get_by_id_or_none(student_id)
        if student is None:
            raise BusinessException(
                "学生不存在或已删除",
                code=ErrorCode.STUDENT_NOT_FOUND,
            )
        teacher = self._teacher_repo.get_by_id_or_none(teacher_id)
        if teacher is None:
            raise BusinessException(
                "导师不存在或已删除",
                code=ErrorCode.TEACHER_NOT_FOUND,
            )
        self._assert_user_can_participate(
            getattr(student, "user", None), "学生"
        )
        self._assert_user_can_participate(
            getattr(teacher, "user", None), "导师"
        )

        admission = self.repository.create(
            academic_year_id=academic_year_id,
            student_id=student_id,
            teacher_id=teacher_id,
            source=source,
            application=application,
            auto_assignment_log_id=auto_assignment_log_id,
        )
        logger.info(
            "Admission created: id=%s, student=%s, teacher=%s, source=%s",
            admission.id, student_id, teacher_id, source,
        )
        return admission

    @transaction.atomic
    def create_for_application(
        self,
        academic_year_id: int,
        student_id: int,
        teacher_id: int,
        source: int,
        application=None,
    ) -> Admission:
        """为申请创建录取记录（跨聚合写入入口，兼容原签名）

        委托 :meth:`allocate`，从而与人工分配 / 自动分配共用同一锁与名额规则。
        """
        return self.allocate(
            academic_year_id=academic_year_id,
            student_id=student_id,
            teacher_id=teacher_id,
            source=source,
            application=application,
        )

    @transaction.atomic
    def manual_assign(
        self,
        academic_year_id: int,
        student_id: int,
        teacher_id: int,
        operator_user,
    ) -> Admission:
        """管理员人工分配（持久化）

        规则：
        - 仅管理员可操作
        - 系统状态必须为 AUTO_ASSIGN 或 FINISHED
        - 学生本学年不能已有录取（唯一约束 + 加锁校验）
        - 导师名额必须 > 已录取人数（未配置名额 = 已关闭）
        - 学生必须是学生角色、导师必须是导师角色，且账号启用未删除
        - 持久化到 DB（admission 记录），不是前端 store 本地更新
        """
        if getattr(operator_user, "role", None) != UserRole.ADMIN.value:
            raise BusinessException(
                "仅管理员可执行人工分配",
                code=ErrorCode.PERMISSION_DENIED,
            )

        # 系统状态：允许 AUTO_ASSIGN / FINISHED
        state = self._system_state_repo.get_by_academic_year(academic_year_id)
        if state is None:
            raise NotFoundError(f"学年 {academic_year_id} 未初始化系统状态")
        allowed = (
            SystemStateValue.AUTO_ASSIGN.value,
            SystemStateValue.FINISHED.value,
        )
        if state.current_state not in allowed:
            raise StateTransitionError(
                "当前系统状态不允许人工分配（仅允许 AUTO_ASSIGN / FINISHED）"
            )

        # 角色校验（在加锁前做便宜校验，避免无谓加锁）
        student_user = self._get_user(student_id)
        if student_user is None or student_user.role != UserRole.STUDENT.value:
            raise BusinessException(
                "指定用户不是学生",
                code=ErrorCode.ROLE_MISMATCH,
            )
        teacher_user = self._get_user(teacher_id)
        if teacher_user is None or teacher_user.role != UserRole.TEACHER.value:
            raise BusinessException(
                "指定用户不是导师",
                code=ErrorCode.ROLE_MISMATCH,
            )

        admission = self.allocate(
            academic_year_id=academic_year_id,
            student_id=student_id,
            teacher_id=teacher_id,
            source=AdmissionSource.MANUAL.value,
        )
        log_business_event(
            action="MANUAL_ASSIGN",
            user_id=operator_user.id,
            target=f"admission:student={student_id},teacher={teacher_id}",
            detail=f"year={academic_year_id}",
        )
        return admission

    @staticmethod
    def _get_user(user_id: int):
        from apps.users.repositories import UserRepository

        return UserRepository().get_by_id_or_none(user_id)

    @transaction.atomic
    def delete_for_application(self, application) -> int:
        """删除与该**申请精确关联**的录取记录（取消第二轮申请）

        只匹配 ``application_id``（可选叠加来源白名单），
        **绝不**按「学生」删除 —— 避免误删人工分配 / 自动分配产生的、
        与该申请无关的录取记录。返回删除条数（正常为 1，恰好释放一个名额）。

        必须在 transaction.atomic 内调用（调用方已持学生行 + 申请行锁）。
        """
        deleted_count = self.repository.delete_by_application(
            application.id,
            sources=(AdmissionSource.ADMIT_ROUND2.value,),
        )
        if deleted_count:
            logger.info(
                "Admission deleted for application: app=%s, student=%s, count=%s",
                application.id, application.student_id, deleted_count,
            )
        return deleted_count

    @transaction.atomic
    def delete_by_year_student(
        self, academic_year_id: int, student_id: int
    ) -> int:
        """按学年+学生删除录取记录

        .. deprecated::
            取消第二轮申请已改用 :meth:`delete_for_application`。
            本方法按学生删除任意来源的录取，可能误删人工/自动分配结果，
            仅为兼容历史调用方保留，新代码不应使用。
        """
        deleted_count = self.repository.delete_by_year_student(
            academic_year_id, student_id
        )
        if deleted_count:
            logger.info(
                "Admission deleted: year=%s, student=%s, count=%s",
                academic_year_id, student_id, deleted_count,
            )
        return deleted_count


@dataclass
class SeatContext:
    """锁定后的座位不变量快照"""

    academic_year_id: int
    teacher_id: int
    student_id: int | None
    student: object | None
    quota: object | None
    max_quota: int | None
    admitted_count: int
    remaining_quota: int | None


class AutoAssignmentLogService(BaseService):
    """自动分配日志业务服务（只读）"""

    repository = AutoAssignmentLogRepository()

    def list(self, filters: dict | None = None, order_by: list | None = None):
        """查询自动分配日志列表，默认按 ID 倒序"""
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> AutoAssignmentLog:
        return self.repository.get_by_id(pk)

    def list_by_academic_year(self, academic_year_id: int):
        """按学年查询自动分配日志"""
        return self.repository.list_by_academic_year(academic_year_id)


# ===== 自动分配算法 =====


@dataclass
class AssignmentPreview:
    """分配预览结果（单个学生）"""

    student_id: int
    student_name: str
    student_number: str
    teacher_id: int
    teacher_name: str
    teacher_number: str
    remaining_quota: int


@dataclass
class AutoAssignmentResult:
    """自动分配结果"""

    log_id: int | None = None
    total_unassigned: int = 0
    assigned_count: int = 0
    failed_count: int = 0
    is_dry_run: bool = False
    is_all_assigned: bool = False
    previews: list[AssignmentPreview] = field(default_factory=list)
    error: str | None = None


class AutoAssignmentService:
    """自动分配服务

    严格按照 DATABASE.md 7.7 实现：
    - 分布式锁防并发（辅助手段，正确性由 DB 行锁保证）
    - 逐条独立事务
    - 容量限制（remaining_quota > 0，当前读）
    - 已录取过滤（无 admission 的学生）
    - 导师编号排序（剩余名额降序 + teacher_number 升序）
    - 公平分配（每次取剩余名额最多的导师）

    支持 Dry Run（预览不实际分配）和 Revoke（撤销）。
    """

    # ===== 主入口 =====

    @classmethod
    def run(
        cls,
        academic_year_id: int,
        triggered_by: int | None = None,
        dry_run: bool = False,
    ) -> AutoAssignmentResult:
        """执行自动分配

        Args:
            academic_year_id: 学年 ID
            triggered_by: 触发用户 ID
            dry_run: 是否仅预览（不实际创建 admission）

        Returns:
            AutoAssignmentResult 分配结果
        """
        # 1. 获取分布式锁（辅助：降低并发冲突；不作为正确性依据）
        lock_key = lock_auto_assign(academic_year_id)
        lock = DistributedLock(lock_key, ttl=LOCK_TTL_AUTO_ASSIGN)

        if not lock.acquire():
            raise LockAcquisitionError(
                f"自动分配任务正在执行: year={academic_year_id}"
            )

        start = time.perf_counter()
        success = False
        try:
            result = cls._do_run(academic_year_id, triggered_by, dry_run, lock)
            success = True
            return result
        except Exception as exc:
            logger.error(
                "Auto assignment failed: year=%s, error=%s",
                academic_year_id, exc,
            )
            raise
        finally:
            lock.release()
            MetricsService.record_assignment(success, time.perf_counter() - start)

    # ===== 核心逻辑 =====

    @classmethod
    def _do_run(
        cls,
        academic_year_id: int,
        triggered_by: int | None,
        dry_run: bool,
        lock: DistributedLock,
    ) -> AutoAssignmentResult:
        """核心分配逻辑"""

        # 2. 校验 system_state = AUTO_ASSIGN
        state_service = SystemStateService()
        if not state_service.is_state(academic_year_id, SystemStateValue.AUTO_ASSIGN.value):
            raise StateTransitionError(
                f"当前状态不是 AUTO_ASSIGN，无法执行自动分配: year={academic_year_id}"
            )

        # 3. 校验当前无运行中自动分配任务
        log_repo = AutoAssignmentLogRepository()
        running_logs = log_repo.get_running_by_year(academic_year_id)
        if running_logs.exists():
            raise BusinessException(
                f"已有运行中的自动分配任务: year={academic_year_id}"
            )

        # 4. 查询未分配学生列表（当前学年无 admission）
        unassigned_students = cls._get_unassigned_students(academic_year_id)

        # 5. 查询有剩余名额的导师列表
        available_teachers = cls._get_available_teachers(academic_year_id)

        # Dry Run: 仅返回预览，不实际分配
        if dry_run:
            previews = cls._generate_preview(
                unassigned_students, available_teachers
            )
            return AutoAssignmentResult(
                total_unassigned=len(unassigned_students),
                assigned_count=len(previews),
                failed_count=len(unassigned_students) - len(previews),
                is_dry_run=True,
                is_all_assigned=len(previews) == len(unassigned_students),
                previews=previews,
            )

        # 记录分配开始（参与者数量）
        MetricsService.record_assignment_start({
            "students": len(unassigned_students),
            "teachers": len(available_teachers),
        })
        try:
            # 6. 创建 auto_assignment_log
            from apps.users.repositories import UserRepository

            user_repo = UserRepository()
            triggered_user = None
            if triggered_by:
                triggered_user = user_repo.get_by_id_or_none(triggered_by)
                if triggered_user is None:
                    logger.warning("Triggered user not found: id=%s", triggered_by)

            log = log_repo.create(
                academic_year_id=academic_year_id,
                status=AutoAssignmentStatus.RUNNING.value,
                total_unassigned=len(unassigned_students),
                triggered_by=triggered_user,
                started_at=timezone.now(),
            )

            result = AutoAssignmentResult(
                log_id=log.id,
                total_unassigned=len(unassigned_students),
            )

            # 7. 对每个未分配学生（独立事务）
            for student in unassigned_students:
                success = cls._assign_single_student(
                    academic_year_id, student, log.id
                )
                if success:
                    result.assigned_count += 1
                else:
                    result.failed_count += 1

            # 8. 更新 auto_assignment_log
            if result.failed_count == 0:
                final_status = AutoAssignmentStatus.SUCCESS.value
            elif result.assigned_count > 0:
                final_status = AutoAssignmentStatus.PARTIAL.value
            else:
                final_status = AutoAssignmentStatus.FAILED.value

            log_repo.update(log, {
                "status": final_status,
                "assigned_count": result.assigned_count,
                "failed_count": result.failed_count,
                "finished_at": timezone.now(),
            })

            # 9. 若全部学生已分配，状态转换 AUTO_ASSIGN → FINISHED
            result.is_all_assigned = result.failed_count == 0
            if result.is_all_assigned:
                try:
                    state_service.forward(academic_year_id, operator_user=triggered_user)
                    logger.info(
                        "Auto assignment completed, state -> FINISHED: year=%s",
                        academic_year_id,
                    )
                except Exception as exc:
                    logger.error(
                        "State transition to FINISHED failed: year=%s, error=%s",
                        academic_year_id, exc,
                    )

            logger.info(
                "Auto assignment done: year=%s, total=%d, assigned=%d, failed=%d",
                academic_year_id,
                result.total_unassigned,
                result.assigned_count,
                result.failed_count,
            )

            return result
        finally:
            MetricsService.record_assignment_end()

    # ===== 辅助方法 =====

    @staticmethod
    def _get_unassigned_students(academic_year_id: int) -> list[StudentProfile]:
        """查询未分配学生列表（当前学年无 admission）

        依据 DATABASE.md 7.7 第 4 步：
        查询当前学年无 admission 的学生。

        Service 层负责跨模块编排：先从 AdmissionRepository 获取已录取学生 ID，
        再传入 StudentProfileRepository 排除（保持 Repository 层模块独立性）。
        """
        from apps.students.repositories import StudentProfileRepository

        admission_repo = AdmissionRepository()
        student_repo = StudentProfileRepository()

        assigned_ids = admission_repo.list_assigned_student_ids(academic_year_id)
        return student_repo.list_unassigned(excluded_user_ids=assigned_ids)

    @staticmethod
    def _get_available_teachers(academic_year_id: int) -> list[dict]:
        """查询有剩余名额的导师列表

        依据 DATABASE.md 7.7 第 5 步：
        按剩余名额降序 + teacher_number 升序排序

        Returns:
            [{"teacher_id": int, "teacher_number": str, "name": str,
              "max_quota": int, "admitted_count": int, "remaining_quota": int}]
        """
        quota_repo = TeacherQuotaRepository()
        teachers = quota_repo.list_with_remaining(academic_year_id)
        # 只返回有剩余名额的
        return [t for t in teachers if t["remaining_quota"] > 0]

    @staticmethod
    def _generate_preview(
        students: list[StudentProfile],
        teachers: list[dict],
    ) -> list[AssignmentPreview]:
        """生成分配预览（Dry Run）

        模拟分配过程，不实际创建 admission。
        """
        previews = []
        # 复制导师剩余名额（避免修改原列表）
        teacher_remaining = {t["teacher_id"]: t["remaining_quota"] for t in teachers}
        sorted_teachers = list(teachers)  # 已排序

        for student in students:
            # 找剩余名额最多的导师
            available = [t for t in sorted_teachers if teacher_remaining[t["teacher_id"]] > 0]
            if not available:
                break

            # 取第一个（剩余名额最多 + teacher_number 最小）
            teacher = available[0]
            teacher_remaining[teacher["teacher_id"]] -= 1

            previews.append(AssignmentPreview(
                student_id=student.user_id,
                student_name=student.name,
                student_number=student.student_number,
                teacher_id=teacher["teacher_id"],
                teacher_name=teacher["name"],
                teacher_number=teacher["teacher_number"],
                remaining_quota=teacher_remaining[teacher["teacher_id"]],
            ))

            # 重新排序（因为剩余名额变化了）
            sorted_teachers.sort(
                key=lambda t: (-teacher_remaining[t["teacher_id"]], t["teacher_number"])
            )

        return previews

    @classmethod
    def _assign_single_student(
        cls,
        academic_year_id: int,
        student: StudentProfile,
        log_id: int,
    ) -> bool:
        """分配单个学生（独立事务）

        依据 DATABASE.md 7.7 第 7 步，但加锁顺序、名额判定与**参与方校验**
        全部统一到 ``AdmissionService.allocate``（不再直接 create 绕过公共规则）：
        a. 锁学生行
        b. SELECT teacher_quota ... FOR UPDATE（本学年全部名额行）
        c. **当前读**统计 admitted（绕过 REPEATABLE READ 过期快照）
        d. 选取 remaining_quota > 0 且剩余最多的导师
        e. 调用 ``AdmissionService.allocate``（同一事务内重入加锁安全：
           同一行锁在同一事务内可重入）→ 由 allocate 统一完成名额判定、
           学生学年唯一性校验、以及「学生/导师账号存在且启用」校验
        f. 创建 admission (source=AUTO_ASSIGNED)
        失败 → 重试 3 次

        Returns:
            True 表示分配成功
        """
        admission_service = AdmissionService()
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # 固定锁顺序第 1 步：锁学生行
                    if admission_service.lock_student(student.user_id) is None:
                        logger.warning(
                            "Student row missing/skipped: student=%s", student.user_id
                        )
                        return False

                    # 锁名额行 + 当前读计数，选剩余名额最多的导师
                    teacher = cls._select_teacher_with_lock(academic_year_id)
                    if not teacher or teacher["remaining_quota"] <= 0:
                        logger.warning(
                            "No available teacher for student=%s",
                            student.user_id,
                        )
                        return False

                    # 统一入口：与第一轮/第二轮/人工分配共用同一锁协议与名额规则
                    # （含禁用/已删除学生-导师校验，防止自动分配成为绕过口）
                    admission = admission_service.allocate(
                        academic_year_id=academic_year_id,
                        student_id=student.user_id,
                        teacher_id=teacher["teacher_id"],
                        source=AdmissionSource.AUTO_ASSIGNED.value,
                        auto_assignment_log_id=log_id,
                    )

                    logger.debug(
                        "Auto assigned: student=%s -> teacher=%s (admission=%s)",
                        student.user_id, teacher["teacher_id"], admission.id,
                    )
                    log_business_event(
                        action="AUTO_ASSIGN",
                        target=f"admission:student={student.user_id},teacher={teacher['teacher_id']}",
                        detail=f"year={academic_year_id},log={log_id}",
                    )
                    return True

            except Exception as exc:
                logger.warning(
                    "Assign attempt %d failed: student=%s, error=%s",
                    attempt + 1, student.user_id, exc,
                )
                if attempt == max_retries - 1:
                    return False

        return False

    @staticmethod
    def _select_teacher_with_lock(academic_year_id: int) -> dict | None:
        """选择导师（带行锁 + 当前读计数）

        依据 DATABASE.md 7.7 第 7a 步：
        SELECT teacher_quota ... FOR UPDATE（按剩余名额降序 + teacher_number 升序
        取第一个 remaining > 0）。

        注意：``list_with_remaining(for_update=True)`` 内部先锁 teacher_quota 行，
        再用当前读统计 admitted，因此返回的 remaining_quota 是**加锁后的真实值**，
        不会因 REPEATABLE READ 快照而偏大。

        Returns:
            导师信息字典，无可用导师返回 None
        """
        quota_repo = TeacherQuotaRepository()
        teachers = quota_repo.list_with_remaining(academic_year_id, for_update=True)
        # 只返回有剩余名额的，取第一个（已按剩余名额降序+teacher_number升序排序）
        available = [t for t in teachers if t["remaining_quota"] > 0]
        return available[0] if available else None

    # ===== 撤销自动分配（DATABASE.md 7.8） =====

    @classmethod
    @transaction.atomic
    def revoke(
        cls,
        academic_year_id: int,
        auto_assignment_log_id: int,
        revoked_by: int | None = None,
    ) -> dict:
        """撤销自动分配

        依据 DATABASE.md 7.8：
        1. 读取 auto_assignment_log（**FOR UPDATE**，真实加锁）
        2. 校验日志属于传入学年（防止跨学年误撤销）
        3. 校验状态不是 RUNNING（运行中的任务不可撤销）
        4. 校验 is_revoked = 0
        5. DELETE FROM admission WHERE auto_assignment_log_id=? AND source=AUTO_ASSIGNED
        6. 更新 auto_assignment_log SET is_revoked=1, revoked_at=NOW(), revoked_by=?
        7. 写入 operation_log (action=REVOKE_AUTO_ASSIGN)

        Args:
            academic_year_id: 学年 ID（必须与日志所属学年一致）
            auto_assignment_log_id: 自动分配日志 ID
            revoked_by: 撤销用户 ID

        Returns:
            {"revoked_count": int, "log_id": int}
        """
        start = time.perf_counter()
        success = False
        try:
            from apps.users.repositories import UserRepository

            # 1. 读取 auto_assignment_log（行锁）
            log_repo = AutoAssignmentLogRepository()
            log = log_repo.get_by_id_for_update(auto_assignment_log_id)
            if log is None:
                raise BusinessException(
                    f"自动分配日志不存在: id={auto_assignment_log_id}"
                )

            # 2. 学年必须匹配（防止用错误学年撤销其它学年的批次）
            if log.academic_year_id != academic_year_id:
                raise BusinessException(
                    "自动分配日志与指定学年不匹配",
                    code=ErrorCode.PARAM_INVALID,
                )

            # 3. 运行中的批次不可撤销
            if log.status == AutoAssignmentStatus.RUNNING.value:
                raise BusinessException(
                    "自动分配任务正在运行，无法撤销",
                    code=ErrorCode.AUTO_ASSIGN_RUNNING,
                )

            # 4. 校验 is_revoked = 0
            if log.is_revoked:
                raise BusinessException(
                    f"该自动分配已撤销: id={auto_assignment_log_id}"
                )

            # 5. 删除 source=AUTO_ASSIGNED 的 admission
            admission_repo = AdmissionRepository()
            deleted_count = admission_repo.delete_auto_assigned_by_log(auto_assignment_log_id)

            # 6. 更新 auto_assignment_log
            user_repo = UserRepository()
            revoked_user = None
            if revoked_by:
                revoked_user = user_repo.get_by_id_or_none(revoked_by)
                if revoked_user is None:
                    logger.warning("Revoked user not found: id=%s", revoked_by)

            log_repo.update(log, {
                "is_revoked": True,
                "revoked_at": timezone.now(),
                "revoked_by": revoked_user,
                "status": AutoAssignmentStatus.REVOKED.value,
            })

            logger.info(
                "Auto assignment revoked: log_id=%s, deleted=%d, by=%s",
                auto_assignment_log_id, deleted_count, revoked_by,
            )
            # 写入 operation_log（DATABASE.md 7.8 第 7 步）
            log_business_event(
                action="REVOKE_AUTO_ASSIGN",
                user_id=revoked_by,
                target=f"auto_assignment_log:{auto_assignment_log_id}",
                detail=f"year={academic_year_id},revoked={deleted_count}",
            )

            success = True
            return {
                "revoked_count": deleted_count,
                "log_id": auto_assignment_log_id,
            }
        finally:
            MetricsService.record_assignment(success, time.perf_counter() - start)

    # ===== 预览（不获取锁） =====

    @classmethod
    def preview(cls, academic_year_id: int) -> dict:
        """获取分配预览（不执行实际分配）

        Returns:
            {
                "total_unassigned": int,
                "available_teachers": int,
                "total_remaining_quota": int,
                "previews": [...],
            }
        """
        unassigned_students = cls._get_unassigned_students(academic_year_id)
        available_teachers = cls._get_available_teachers(academic_year_id)
        previews = cls._generate_preview(unassigned_students, available_teachers)

        return {
            "total_unassigned": len(unassigned_students),
            "available_teachers": len(available_teachers),
            "total_remaining_quota": sum(t["remaining_quota"] for t in available_teachers),
            "previews": [
                {
                    "student_id": p.student_id,
                    "student_name": p.student_name,
                    "student_number": p.student_number,
                    "teacher_id": p.teacher_id,
                    "teacher_name": p.teacher_name,
                    "teacher_number": p.teacher_number,
                }
                for p in previews
            ],
        }
