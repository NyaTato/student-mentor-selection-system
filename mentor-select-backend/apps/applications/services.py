"""
申请管理业务服务

业务规则依据 PROJECT.md：
- R1: 学生在每轮申请中只能提交一个申请（DB 唯一约束 uk_year_student_round）
- R2: 第一轮申请不可删除、不可取消
- R3-02: 第二轮先到先得，无导师审核，立即占用名额
- R3-03: 第二轮点击申请立即占用一个名额
- R3-04: 名额归零时禁止申请
- R3-06: 第二轮可取消申请，取消后释放名额
- R3/R4: 申请状态转换：PENDING -> APPROVED / REJECTED
- R5: 第一轮申请被拒绝后，学生才能提交第二轮申请
- R6: 导师在 TEACHER_REVIEW 状态下审核第一轮申请
- R8: 第一轮已通过的学生不能进入第二轮
- BC-01: 学生提交申请时，系统状态必须匹配轮次
- BC-03: 名额硬约束，录取人数不超过名额（行锁防并发超卖）
- BC-04: 导师审核申请时，系统状态必须匹配轮次

并发安全（v2 业务闭环）：
- 固定锁顺序：**申请行（如存在） -> 学生行 -> teacher_quota 行 -> admission 当前读**
  实际实现顺序为 学生行 -> 申请行 -> 名额行 -> admission 当前读，
  全部路径（第一轮修改 / 审核通过 / 审核拒绝 / 第二轮立即录取 / 取消 / 人工分配 /
  自动分配 / 撤销第一轮录取）遵循同一顺序，避免交叉加锁导致死锁。
- 计数一律使用 AdmissionService 的「锁定座位不变量」helper，
  在 MySQL REPEATABLE READ 下使用当前读，避免过期快照导致的超卖。
"""
from __future__ import annotations

import time

from django.db import transaction

from apps.applications.models import Application
from apps.applications.repositories import ApplicationRepository
from apps.assignments.services import AdmissionService
from apps.common.enums import (
    AdmissionSource,
    ApplicationRound,
    ApplicationStatus,
    SystemStateValue,
    UserRole,
)
from apps.common.error_codes import ErrorCode
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    StateTransitionError,
    ValidationError,
)
from apps.common.logger import get_logger, log_business_event
from apps.common.services import BaseService
from apps.monitoring.services import MetricsService
from apps.system.repositories import SystemStateRepository

logger = get_logger("applications.services")


class ApplicationService(BaseService):
    """申请业务服务"""

    repository = ApplicationRepository()
    # 跨聚合服务：admission 写入与名额锁统一通过 AdmissionService 委托
    _admission_service = AdmissionService()
    _system_state_repo = SystemStateRepository()

    # ===== 查询 =====

    def list(self, filters: dict | None = None, order_by: list | None = None):
        return self.repository.list(filters=filters, order_by=order_by or ["-id"])

    def get_by_id(self, pk: int) -> Application:
        return self.repository.get_by_id(pk)

    def list_my_applications(
        self, student_user_id: int, academic_year_id: int | None = None
    ):
        """学生查询自己的申请"""
        return self.repository.list_by_student(student_user_id, academic_year_id)

    def list_teacher_applications(
        self,
        teacher_user_id: int,
        academic_year_id: int | None = None,
        round_value: int | None = None,
        status: int | None = None,
    ):
        """导师查询收到的申请"""
        return self.repository.list_by_teacher(
            teacher_user_id, academic_year_id, round_value, status
        )

    # ===== 创建申请 =====

    @transaction.atomic
    def create(self, validated_data: dict) -> Application:
        """学生提交申请

        业务规则：
        - BC-01: 第一轮申请要求系统状态 FIRST_ROUND_OPEN
        - BC-01: 第二轮申请要求系统状态 SECOND_ROUND_OPEN
        - BC-02: 第二轮申请前，第一轮申请必须为 REJECTED
        - BC-03: 同学年同轮次只能有一个申请（DB 约束）
        - R8: 第一轮已通过的学生不能提交第二轮申请
        - R3-02: 第二轮先到先得，无导师审核，立即占用名额
        - R3-04: 第二轮名额归零 / 未配置名额时禁止申请

        并发安全：先锁学生行（串行化同一学生的占用），
        第一轮「修改」路径再锁申请行；第二轮录取由 AdmissionService 统一加锁。
        """
        academic_year = validated_data["academic_year"]
        teacher = validated_data["teacher"]
        round_value = validated_data["round"]

        start = time.perf_counter()
        success = False
        try:
            # 获取关联 ID（可能是 ORM 对象或 ID）
            academic_year_id = getattr(academic_year, "id", academic_year)
            if "student" in validated_data:
                student = validated_data["student"]
                student_id = student.pk if hasattr(student, "pk") else student
            else:
                student_id = validated_data["student_id"]
            teacher_id = teacher.pk if hasattr(teacher, "pk") else teacher

            # 固定锁顺序第 1 步：锁学生行（串行化该学生的占用判定）
            self._admission_service.lock_student(student_id)

            # 1. 校验系统状态匹配轮次
            self._validate_system_state_for_submit(academic_year_id, round_value)

            # 2. 校验是否已有同轮次申请（加行锁读取，避免并发双写）
            existing = self.repository.get_by_year_student_round_for_update(
                academic_year_id, student_id, round_value
            )
            if existing is not None:
                # 第二轮已有申请：拒绝（R3-05：第二轮需先取消再重新选）
                if round_value == ApplicationRound.SECOND_ROUND.value:
                    raise BusinessException(
                        f"学生在该学年第 {round_value} 轮已有申请，请先取消再重新选择",
                        code=ErrorCode.APPLICATION_DUPLICATE,
                    )
                # 第一轮已有申请：仅 PENDING 状态允许修改（R1：每轮只能有一条申请）
                if existing.status != ApplicationStatus.PENDING.value:
                    raise BusinessException(
                        "第一轮申请已被审核，无法修改",
                        code=ErrorCode.APPLICATION_ALREADY_PROCESSED,
                    )
                # 第一轮 PENDING 状态：UPDATE（修改导师，状态保持 PENDING）
                application = self.repository.update(
                    existing,
                    {
                        "teacher_id": teacher_id,
                        "status": ApplicationStatus.PENDING.value,
                    },
                )
                logger.info(
                    "Application updated (round1): id=%s, student=%s, new_teacher=%s",
                    application.id, student_id, teacher_id,
                )
                success = True
                return application

            # 3. 第二轮申请的额外校验
            if round_value == ApplicationRound.SECOND_ROUND.value:
                self._validate_second_round_eligibility(academic_year_id, student_id)
                # R3-04: 名额归零 / 未配置名额时禁止申请（与录取路径同一锁规则）
                self._validate_second_round_quota(academic_year_id, teacher_id)

            # 4. 创建申请（通过 Repository）
            # R3-02: 第二轮先到先得，无导师审核，立即 APPROVED
            initial_status = (
                ApplicationStatus.APPROVED.value
                if round_value == ApplicationRound.SECOND_ROUND.value
                else ApplicationStatus.PENDING.value
            )
            application = self.repository.create(
                academic_year_id=academic_year_id,
                student_id=student_id,
                teacher_id=teacher_id,
                round=round_value,
                status=initial_status,
            )

            # 5. R3-03: 第二轮立即占用名额 — 统一走 AdmissionService 锁定座位不变量
            if round_value == ApplicationRound.SECOND_ROUND.value:
                self._admission_service.create_for_application(
                    academic_year_id=academic_year_id,
                    student_id=student_id,
                    teacher_id=teacher_id,
                    source=AdmissionSource.ADMIT_ROUND2.value,
                    application=application,
                )
                logger.info(
                    "Second round auto-admitted: app=%s, student=%s, teacher=%s",
                    application.id, student_id, teacher_id,
                )

            logger.info(
                "Application created: id=%s, student=%s, teacher=%s, round=%s",
                application.id, student_id, teacher_id, round_value,
            )
            success = True
            return application
        finally:
            MetricsService.record_application(
                round_value, success, time.perf_counter() - start
            )

    # ===== 导师审核 =====

    @transaction.atomic
    def approve(self, application_id: int, operator_user) -> Application:
        """导师通过申请

        业务规则：
        - BC-04: 第一轮审核要求系统状态 TEACHER_REVIEW
        - BC-04: 第二轮审核要求系统状态 SECOND_ROUND_OPEN
        - 申请状态必须为 PENDING
        - 操作者必须是该申请的导师
        - BC-03: 通过时创建 admission 记录（第一轮 source=ADMIT_ROUND1），
          名额校验在 AdmissionService 内统一完成（未配置名额 = 不录取）
        """
        start = time.perf_counter()
        success = False
        try:
            application = self._transition_status(
                application_id, operator_user, ApplicationStatus.APPROVED.value, "approved"
            )
            # 创建 admission 记录（仅第一轮需要，第二轮在 create 时已创建）
            if application.round == ApplicationRound.FIRST_ROUND.value:
                self._create_admission_for_first_round(application)
            success = True
            return application
        finally:
            MetricsService.record_review(
                passed=success, duration=time.perf_counter() - start
            )

    @transaction.atomic
    def reject(self, application_id: int, operator_user) -> Application:
        """导师拒绝申请"""
        start = time.perf_counter()
        success = False
        try:
            application = self._transition_status(
                application_id, operator_user, ApplicationStatus.REJECTED.value, "rejected"
            )
            success = True
            return application
        finally:
            MetricsService.record_review(
                passed=False, duration=time.perf_counter() - start
            )

    @transaction.atomic
    def _transition_status(
        self,
        application_id: int,
        operator_user,
        target_status: int,
        action_name: str,
    ) -> Application:
        """审核申请的通用流程（通过/拒绝共用）

        固定锁顺序：学生行 -> 申请行。先在无锁读中取得 student_id，
        再按顺序加锁并**重新校验**（防止两次读取之间状态被并发改变）。
        """
        # 1. 无锁读取（仅用于取得 student_id 并尽早做归属校验）
        application = self.repository.get_by_id(application_id)
        self._validate_teacher_ownership(application, operator_user)

        # 2. 固定锁顺序：锁学生行 -> 锁申请行
        self._admission_service.lock_student(application.student_id)
        application = self.repository.get_by_id_for_update(application_id)
        if application is None:
            raise NotFoundError(f"Application (id={application_id}) 不存在")

        # 3. 加锁后重新校验
        self._validate_teacher_ownership(application, operator_user)

        if application.status != ApplicationStatus.PENDING.value:
            raise BusinessException(
                "该申请已被处理，无法重复操作",
                code=ErrorCode.APPLICATION_ALREADY_PROCESSED,
            )

        self._validate_system_state_for_review(
            application.academic_year_id, application.round
        )

        # 通过 Repository 更新状态（含乐观锁版本递增）
        application = self.repository.update(
            application, {"status": target_status}
        )

        logger.info(
            "Application %s: id=%s, teacher=%s",
            action_name, application_id, operator_user.id,
        )
        return application

    @transaction.atomic
    def batch_approve(self, application_ids: list[int], operator_user) -> list[Application]:
        """导师批量通过申请"""
        result = []
        for app_id in application_ids:
            try:
                app = self.approve(app_id, operator_user)
                result.append(app)
            except BusinessException as e:
                logger.warning(
                    "Batch approve skip application %s: %s", app_id, e.detail
                )
        return result

    @transaction.atomic
    def batch_reject(self, application_ids: list[int], operator_user) -> list[Application]:
        """导师批量拒绝申请"""
        result = []
        for app_id in application_ids:
            try:
                app = self.reject(app_id, operator_user)
                result.append(app)
            except BusinessException as e:
                logger.warning(
                    "Batch reject skip application %s: %s", app_id, e.detail
                )
        return result

    # ===== 撤销第一轮录取（R2-04：导师筛选阶段内可修改） =====

    @transaction.atomic
    def revoke_approval(self, application_id: int, operator_user) -> Application:
        """导师撤销第一轮已通过的录取（持久化，非前端本地内存）

        业务规则：
        - 操作者必须是该申请的导师（管理员按现有归属 helper 放行）
        - 申请必须是**第一轮**且状态为 APPROVED
        - 学年系统状态必须仍为 TEACHER_REVIEW（阶段推进后不可撤销）
        - 只删除与该申请**精确关联**且来源为 ADMIT_ROUND1 的录取记录
          （恰好释放一个名额），绝不按「学生」删除，避免误删人工分配 /
          自动分配 / 第二轮录取
        - 删除行数必须恰好为 1，否则整体回滚
        - 申请置为 REJECTED，使学生重新获得第二轮资格（R5）

        固定锁顺序：学生行 -> 申请行 -> teacher_quota 行 -> admission 当前读。
        """
        # 1. 无锁读取（仅用于取得 student_id 并尽早做归属校验）
        application = self.repository.get_by_id(application_id)
        self._validate_teacher_ownership(application, operator_user)

        # 2. 固定锁顺序：锁学生行 -> 锁申请行
        self._admission_service.lock_student(application.student_id)
        application = self.repository.get_by_id_for_update(application_id)
        if application is None:
            raise NotFoundError(f"Application (id={application_id}) 不存在")

        # 3. 加锁后重新校验归属 / 轮次 / 状态 / 阶段
        self._validate_teacher_ownership(application, operator_user)

        if application.round != ApplicationRound.FIRST_ROUND.value:
            raise BusinessException(
                "仅第一轮已通过的申请可撤销录取",
                code=ErrorCode.APPLICATION_STATUS_INVALID,
            )
        if application.status != ApplicationStatus.APPROVED.value:
            raise BusinessException(
                "该申请不是已通过状态，无法撤销录取",
                code=ErrorCode.APPLICATION_ALREADY_PROCESSED,
            )

        self._validate_system_state_for_review(
            application.academic_year_id, ApplicationRound.FIRST_ROUND.value
        )

        # 4. 锁顺序第 3-4 步：teacher_quota 行锁 + admission 当前读
        #    （与其他分配路径共用同一「锁定座位不变量」协议，防死锁/超卖）
        self._admission_service.lock_seat_invariant(
            application.academic_year_id, application.teacher_id
        )

        # 5. 精确删除：application_id + source=ADMIT_ROUND1，缺一不可
        #    复用 AdmissionService 的 Repository（同一 delete_by_application，
        #    带 sources 白名单），因为 delete_for_application 固定为第二轮来源。
        deleted_count = self._admission_service.repository.delete_by_application(
            application.id, sources=(AdmissionSource.ADMIT_ROUND1.value,)
        )
        if deleted_count != 1:
            raise BusinessException(
                "未找到与该申请对应的第一轮录取记录，撤销失败",
                code=ErrorCode.ADMISSION_NOT_FOUND,
            )

        # 6. 申请置为 REJECTED（重新获得第二轮资格），走 Repository 乐观锁版本递增
        application = self.repository.update(
            application, {"status": ApplicationStatus.REJECTED.value}
        )

        logger.info(
            "Admission revoked (round1): app=%s, teacher=%s",
            application_id, operator_user.id,
        )
        # 审计日志：仅记录 ID，不含姓名/学号等个人数据
        log_business_event(
            action="REVOKE_ADMISSION",
            user_id=operator_user.id,
            target=f"application:{application_id}",
            detail=f"year={application.academic_year_id}",
        )
        return application

    # ===== 业务校验 =====

    def _get_system_state(self, academic_year_id: int):
        """获取学年对应的系统状态（通过 Repository）"""
        state = self._system_state_repo.get_by_academic_year(academic_year_id)
        if state is None:
            raise NotFoundError(
                f"学年 {academic_year_id} 未初始化系统状态",
            )
        return state

    def _validate_system_state_for_submit(
        self, academic_year_id: int, round_value: int
    ) -> None:
        """校验提交申请时的系统状态"""
        state = self._get_system_state(academic_year_id)

        if round_value == ApplicationRound.FIRST_ROUND.value:
            required = SystemStateValue.FIRST_ROUND_OPEN.value
            msg = "第一轮申请未开放，当前状态不允许提交"
        elif round_value == ApplicationRound.SECOND_ROUND.value:
            required = SystemStateValue.SECOND_ROUND_OPEN.value
            msg = "第二轮申请未开放，当前状态不允许提交"
        else:
            raise ValidationError(f"非法轮次: {round_value}")

        if state.current_state != required:
            raise StateTransitionError(msg)

    def _validate_system_state_for_review(
        self, academic_year_id: int, round_value: int
    ) -> None:
        """校验审核申请时的系统状态"""
        state = self._get_system_state(academic_year_id)

        if round_value == ApplicationRound.FIRST_ROUND.value:
            required = SystemStateValue.TEACHER_REVIEW.value
            msg = "当前不是导师审核阶段，无法审核第一轮申请"
        elif round_value == ApplicationRound.SECOND_ROUND.value:
            required = SystemStateValue.SECOND_ROUND_OPEN.value
            msg = "第二轮申请未开放，无法审核第二轮申请"
        else:
            raise ValidationError(f"非法轮次: {round_value}")

        if state.current_state != required:
            raise StateTransitionError(msg)

    def _validate_second_round_eligibility(
        self, academic_year_id: int, student_id: int
    ) -> None:
        """校验学生是否有资格提交第二轮申请

        业务规则：
        - R5: 第一轮申请必须存在且为 REJECTED 状态
        - R8: 第一轮已通过的学生不能提交第二轮
        """
        first_round_status = self.repository.get_first_round_status(
            student_id, academic_year_id
        )

        if first_round_status is None:
            raise BusinessException(
                "请先提交第一轮申请",
                code=ErrorCode.APPLICATION_LIMIT_EXCEEDED,
            )

        if first_round_status == ApplicationStatus.APPROVED.value:
            raise BusinessException(
                "第一轮申请已通过，无需提交第二轮",
                code=ErrorCode.APPLICATION_LIMIT_EXCEEDED,
            )

        if first_round_status != ApplicationStatus.REJECTED.value:
            raise BusinessException(
                "第一轮申请未拒绝，无法提交第二轮",
                code=ErrorCode.APPLICATION_LIMIT_EXCEEDED,
            )

    def _validate_second_round_quota(
        self, academic_year_id: int, teacher_id: int
    ) -> None:
        """R3-04: 校验第二轮导师名额是否还有剩余

        与录取路径共用 AdmissionService 的锁定座位不变量：
        - 锁 quota 行 + admission 当前读计数（REPEATABLE READ 下防过期快照）
        - **未配置 TeacherQuota 视为「已关闭」，不允许申请**（不再是「跳过校验」）

        必须在 transaction.atomic 内调用（调用方 create 已持学生行锁）。
        """
        ctx = self._admission_service.lock_seat_invariant(
            academic_year_id, teacher_id
        )
        self._admission_service.assert_seat_available(ctx)

    def _create_admission_for_first_round(self, application: Application) -> None:
        """第一轮审核通过 — 通过 AdmissionService 创建 admission（source=ADMIT_ROUND1）

        BC-03: 名额硬约束。名额校验与锁完全由 AdmissionService 统一处理
        （未配置名额 = 不录取，避免「无配置即可无限录取」）。
        """
        self._admission_service.create_for_application(
            academic_year_id=application.academic_year_id,
            student_id=application.student_id,
            teacher_id=application.teacher_id,
            source=AdmissionSource.ADMIT_ROUND1.value,
            application=application,
        )
        logger.info(
            "Admission created (round1): student=%s, teacher=%s",
            application.student_id, application.teacher_id,
        )

    @transaction.atomic
    def cancel_second_round(
        self, application_id: int, operator_user
    ) -> Application:
        """R3-06: 学生取消第二轮申请

        业务规则：
        - 仅第二轮申请可取消
        - 系统状态必须为 SECOND_ROUND_OPEN
        - **只删除与该申请精确关联的录取记录**（恰好释放一个名额），
          绝不按「学生」删除，避免误删人工分配 / 自动分配产生的录取
        - 删除申请记录（允许学生重新选择其他导师，通过 Repository）
        - 操作者必须是申请的学生

        固定锁顺序：学生行 -> 申请行（加锁后重新校验归属与轮次）。
        """
        application = self.repository.get_by_id(application_id)

        # 校验操作者是学生本人
        if operator_user.role != UserRole.STUDENT.value:
            raise BusinessException(
                "仅学生可取消自己的申请",
                code=ErrorCode.PERMISSION_DENIED,
            )
        if application.student_id != operator_user.id:
            raise BusinessException(
                "只能取消自己的申请",
                code=ErrorCode.PERMISSION_DENIED,
            )

        # 校验是第二轮申请
        if application.round != ApplicationRound.SECOND_ROUND.value:
            raise BusinessException(
                "仅第二轮申请可取消",
                code=ErrorCode.APPLICATION_LIMIT_EXCEEDED,
            )

        # 固定锁顺序：学生行 -> 申请行
        self._admission_service.lock_student(application.student_id)
        application = self.repository.get_by_id_for_update(application_id)
        if application is None:
            raise NotFoundError(f"Application (id={application_id}) 不存在")

        # 加锁后重新校验
        if application.student_id != operator_user.id:
            raise BusinessException(
                "只能取消自己的申请",
                code=ErrorCode.PERMISSION_DENIED,
            )
        if application.round != ApplicationRound.SECOND_ROUND.value:
            raise BusinessException(
                "仅第二轮申请可取消",
                code=ErrorCode.APPLICATION_LIMIT_EXCEEDED,
            )

        # 校验系统状态
        self._validate_system_state_for_submit(
            application.academic_year_id, ApplicationRound.SECOND_ROUND.value
        )

        # R3-07: 只删除与该申请精确关联的第二轮录取记录（释放恰好一个名额）
        self._admission_service.delete_for_application(application)

        # 通过 Repository 删除申请记录（允许学生重新选择）
        self.repository.hard_delete(application)
        logger.info(
            "Application cancelled (round2): id=%s, student=%s",
            application_id, operator_user.id,
        )
        return application

    def _validate_teacher_ownership(self, application: Application, operator_user) -> None:
        """校验操作者是否为申请的导师

        管理员可绕过此校验。
        """
        if operator_user.role == UserRole.ADMIN.value:
            return

        if operator_user.role != UserRole.TEACHER.value:
            raise BusinessException(
                "仅导师或管理员可审核申请",
                code=ErrorCode.PERMISSION_DENIED,
            )

        # 通过 user_id 反查 teacher_profile
        teacher_profile = getattr(operator_user, "teacher_profile", None)
        if teacher_profile is None or teacher_profile.user_id != application.teacher_id:
            raise BusinessException(
                "只能审核自己的申请",
                code=ErrorCode.PERMISSION_DENIED,
            )
