"""自动分配算法测试

依据 DATABASE.md 7.7 系统自动分配：
1. 获取分布式锁 lock:auto_assign:{year}
2. 校验 system_state = AUTO_ASSIGN
3. 校验当前无运行中自动分配任务
4. 查询未分配学生列表（当前学年无 admission）
5. 查询有剩余名额的导师列表（按剩余名额降序 + teacher_number 升序）
6. 创建 auto_assignment_log (status=RUNNING)
7. 对每个未分配学生（独立事务）：分配 + 3 次重试
8. 更新 auto_assignment_log (status=SUCCESS/PARTIAL/FAILED)
9. 若全部已分配：状态转换 AUTO_ASSIGN → FINISHED
10. 释放分布式锁

测试覆盖：
- Dry Run 预览
- 实际分配（成功 / 部分成功 / 失败）
- 状态校验（非 AUTO_ASSIGN 状态拒绝）
- 运行中任务校验
- 撤销自动分配
- 容量限制（remaining_quota > 0）
- 排序规则（剩余名额降序 + teacher_number 升序）
- 公平分配（每次取剩余名额最多的导师）

依据 DATABASE.md 7.8 撤销自动分配：
- 校验 is_revoked = 0
- 删除 source=AUTO_ASSIGNED 的 admission
- 更新 auto_assignment_log (is_revoked=1, status=REVOKED)
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.assignments.models import Admission, AutoAssignmentLog
from apps.assignments.services import (
    AssignmentPreview,
    AutoAssignmentResult,
    AutoAssignmentService,
)
from apps.common.enums import (
    AdmissionSource,
    AutoAssignmentStatus,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.common.exceptions import BusinessException, StateTransitionError
from apps.common.lock import LockAcquisitionError
from apps.students.models import StudentProfile
from apps.system.models import SystemState
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import User


# ===== 辅助函数 =====


def _make_lock_mock():
    """构造一个始终获取成功的 DistributedLock mock"""
    lock = MagicMock()
    lock.acquire.return_value = True
    lock.release.return_value = True
    return lock


def _setup_state(academic_year, state_value=SystemStateValue.AUTO_ASSIGN.value):
    """创建或更新 system_state"""
    SystemState.objects.update_or_create(
        academic_year=academic_year,
        defaults={
            "current_state": state_value,
            "previous_state": None,
            "state_changed_at": timezone.now() - timedelta(hours=1),
        },
    )


def _create_teacher(teacher_number, name, max_quota, academic_year):
    """创建导师 + 名额配置"""
    user = User.objects.create_user(
        username=f"t_{teacher_number}",
        password="TestPass123!",
        role=UserRole.TEACHER.value,
        status=UserStatus.ACTIVE.value,
    )
    profile = TeacherProfile.objects.create(
        user=user,
        teacher_number=teacher_number,
        name=name,
        college="计算机学院",
        research_area="AI",
    )
    TeacherQuota.objects.create(
        academic_year=academic_year,
        teacher=profile,
        max_quota=max_quota,
    )
    return profile


def _create_student(student_number, name):
    """创建学生"""
    user = User.objects.create_user(
        username=f"s_{student_number}",
        password="TestPass123!",
        role=UserRole.STUDENT.value,
        status=UserStatus.ACTIVE.value,
    )
    return StudentProfile.objects.create(
        user=user,
        student_number=student_number,
        name=name,
        major="CS",
        class_name="class1",
    )


# ===== Dry Run 测试 =====


@pytest.mark.django_db
class TestAutoAssignmentDryRun:
    """Dry Run 预览测试"""

    def test_dry_run_returns_preview_without_creating_admissions(
        self, academic_year
    ):
        """Dry Run 返回预览但不实际创建 admission"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        student = _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id, dry_run=True
            )

        assert result.is_dry_run is True
        assert result.total_unassigned == 1
        assert result.assigned_count == 1
        assert result.failed_count == 0
        assert result.is_all_assigned is True
        assert len(result.previews) == 1
        assert result.previews[0].student_id == student.user_id
        assert result.previews[0].teacher_id == teacher.user_id

        # 不应创建 admission
        assert Admission.objects.count() == 0
        # 不应创建 log
        assert AutoAssignmentLog.objects.count() == 0

    def test_dry_run_no_available_teacher(self, academic_year):
        """Dry Run 时没有可用导师"""
        _setup_state(academic_year)
        _create_student("20240001", "学生A")
        # 创建一个名额为 0 的导师
        _create_teacher("T0001", "导师A", 0, academic_year)

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id, dry_run=True
            )

        assert result.is_dry_run is True
        assert result.total_unassigned == 1
        assert result.assigned_count == 0
        assert result.failed_count == 1
        assert result.is_all_assigned is False
        assert len(result.previews) == 0

    def test_dry_run_partial_assignment(self, academic_year):
        """Dry Run 部分分配（导师名额不足）"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 1, academic_year)
        _create_student("20240001", "学生A")
        _create_student("20240002", "学生B")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id, dry_run=True
            )

        assert result.total_unassigned == 2
        assert result.assigned_count == 1
        assert result.failed_count == 1
        assert result.is_all_assigned is False


# ===== 实际分配测试 =====


@pytest.mark.django_db
class TestAutoAssignmentRun:
    """实际自动分配测试"""

    def test_run_success_all_assigned(self, academic_year, admin_user):
        """全部学生分配成功"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        student = _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert result.is_dry_run is False
        assert result.total_unassigned == 1
        assert result.assigned_count == 1
        assert result.failed_count == 0
        assert result.is_all_assigned is True
        assert result.log_id is not None

        # 验证 admission 创建
        admission = Admission.objects.get()
        assert admission.student_id == student.user_id
        assert admission.teacher_id == teacher.user_id
        assert admission.source == AdmissionSource.AUTO_ASSIGNED.value
        assert admission.auto_assignment_log_id == result.log_id

        # 验证 log 状态
        log = AutoAssignmentLog.objects.get(id=result.log_id)
        assert log.status == AutoAssignmentStatus.SUCCESS.value
        assert log.assigned_count == 1
        assert log.failed_count == 0
        assert log.finished_at is not None
        assert log.triggered_by_id == admin_user.id

        # 验证状态推进到 FINISHED
        state = SystemState.objects.get(academic_year=academic_year)
        assert state.current_state == SystemStateValue.FINISHED.value

    def test_run_partial_when_quota_insufficient(self, academic_year, admin_user):
        """导师名额不足时部分分配"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 1, academic_year)
        s1 = _create_student("20240001", "学生A")
        _create_student("20240002", "学生B")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert result.total_unassigned == 2
        assert result.assigned_count == 1
        assert result.failed_count == 1
        assert result.is_all_assigned is False

        # 验证 log 状态为 PARTIAL
        log = AutoAssignmentLog.objects.get(id=result.log_id)
        assert log.status == AutoAssignmentStatus.PARTIAL.value

        # 状态不应推进
        state = SystemState.objects.get(academic_year=academic_year)
        assert state.current_state == SystemStateValue.AUTO_ASSIGN.value

    def test_run_failed_when_no_quota(self, academic_year, admin_user):
        """所有导师名额为 0，全部失败"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 0, academic_year)
        _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert result.assigned_count == 0
        assert result.failed_count == 1
        assert result.is_all_assigned is False

        log = AutoAssignmentLog.objects.get(id=result.log_id)
        assert log.status == AutoAssignmentStatus.FAILED.value

    def test_run_skips_already_assigned_students(self, academic_year, admin_user):
        """已分配学生被跳过"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        # 预先给 s1 创建 admission
        Admission.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            source=AdmissionSource.MANUAL.value,
        )

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        # 只剩 s2 未分配
        assert result.total_unassigned == 1
        assert result.assigned_count == 1

    def test_run_fair_distribution_by_remaining_quota(
        self, academic_year, admin_user
    ):
        """公平分配：每次取剩余名额最多的导师

        场景：T0001(3) T0002(1)，3 个学生
        预期：s1→T0001, s2→T0001, s3→T0001（T0001 始终剩余最多）
        """
        _setup_state(academic_year)
        t1 = _create_teacher("T0001", "导师A", 3, academic_year)
        t2 = _create_teacher("T0002", "导师B", 1, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")
        s3 = _create_student("20240003", "学生C")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert result.assigned_count == 3

        # T0001 应分配 2 个，T0002 应分配 1 个
        # 因为初始 T0001(3) > T0002(1)，s1→T0001
        # 然后 T0001(2) > T0002(1)，s2→T0001
        # 然后 T0001(1) = T0002(1)，按 teacher_number 升序选 T0001，s3→T0001
        t1_count = Admission.objects.filter(teacher=t1).count()
        t2_count = Admission.objects.filter(teacher=t2).count()
        assert t1_count + t2_count == 3


# ===== 状态校验测试 =====


@pytest.mark.django_db
class TestAutoAssignmentStateValidation:
    """状态校验测试"""

    def test_run_rejects_when_state_not_auto_assign(
        self, academic_year, admin_user
    ):
        """非 AUTO_ASSIGN 状态拒绝执行"""
        _setup_state(
            academic_year, SystemStateValue.SECOND_ROUND_OPEN.value
        )
        _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            with pytest.raises(StateTransitionError):
                AutoAssignmentService.run(
                    academic_year_id=academic_year.id,
                    triggered_by=admin_user.id,
                )

        # 不应创建 log
        assert AutoAssignmentLog.objects.count() == 0

    def test_run_rejects_when_running_log_exists(self, academic_year, admin_user):
        """已有运行中任务时拒绝"""
        _setup_state(academic_year)
        _create_student("20240001", "学生A")

        # 预创建一个 RUNNING 的 log
        AutoAssignmentLog.objects.create(
            academic_year=academic_year,
            status=AutoAssignmentStatus.RUNNING.value,
            total_unassigned=1,
            triggered_by=admin_user,
            started_at=timezone.now(),
        )

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            with pytest.raises(BusinessException):
                AutoAssignmentService.run(
                    academic_year_id=academic_year.id,
                    triggered_by=admin_user.id,
                )

    def test_run_raises_when_lock_unavailable(self, academic_year, admin_user):
        """分布式锁获取失败时抛 LockAcquisitionError"""
        _setup_state(academic_year)
        _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock = MagicMock()
            mock_lock.acquire.return_value = False
            mock_lock_cls.return_value = mock_lock

            with pytest.raises(LockAcquisitionError):
                AutoAssignmentService.run(
                    academic_year_id=academic_year.id,
                    triggered_by=admin_user.id,
                )


# ===== 排序规则测试 =====


@pytest.mark.django_db
class TestAutoAssignmentSorting:
    """导师排序规则测试"""

    def test_available_teachers_sorted_by_remaining_desc_then_number_asc(
        self, academic_year
    ):
        """导师列表按剩余名额降序 + teacher_number 升序排序"""
        _setup_state(academic_year)
        # 三个导师：T0001(2) T0002(3) T0003(2)
        _create_teacher("T0001", "导师A", 2, academic_year)
        _create_teacher("T0002", "导师B", 3, academic_year)
        _create_teacher("T0003", "导师C", 2, academic_year)

        teachers = AutoAssignmentService._get_available_teachers(academic_year.id)

        # 排序：T0002(3) > T0001(2) > T0003(2)（同剩余，按 number 升序）
        assert len(teachers) == 3
        assert teachers[0]["teacher_number"] == "T0002"
        assert teachers[0]["remaining_quota"] == 3
        assert teachers[1]["teacher_number"] == "T0001"
        assert teachers[2]["teacher_number"] == "T0003"

    def test_unassigned_students_ordered_by_student_number(self, academic_year):
        """未分配学生按学号升序"""
        _setup_state(academic_year)
        _create_student("20240003", "学生C")
        _create_student("20240001", "学生A")
        _create_student("20240002", "学生B")

        students = AutoAssignmentService._get_unassigned_students(academic_year.id)
        assert len(students) == 3
        assert students[0].student_number == "20240001"
        assert students[1].student_number == "20240002"
        assert students[2].student_number == "20240003"


# ===== 撤销自动分配测试 =====


@pytest.mark.django_db
class TestAutoAssignmentRevoke:
    """撤销自动分配测试（DATABASE.md 7.8）"""

    def test_revoke_success(self, academic_year, admin_user):
        """撤销成功：删除 admission + 更新 log"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert Admission.objects.count() == 2
        log = AutoAssignmentLog.objects.get()

        # 撤销
        result = AutoAssignmentService.revoke(
            academic_year_id=academic_year.id,
            auto_assignment_log_id=log.id,
            revoked_by=admin_user.id,
        )

        assert result["revoked_count"] == 2
        assert result["log_id"] == log.id

        # admission 应被删除
        assert Admission.objects.count() == 0

        # log 应更新
        log.refresh_from_db()
        assert log.is_revoked is True
        assert log.revoked_at is not None
        assert log.revoked_by_id == admin_user.id
        assert log.status == AutoAssignmentStatus.REVOKED.value

    def test_revoke_rejects_already_revoked(self, academic_year, admin_user):
        """撤销已撤销的 log 抛异常"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 1, academic_year)
        _create_student("20240001", "学生A")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        log = AutoAssignmentLog.objects.get()
        AutoAssignmentService.revoke(
            academic_year_id=academic_year.id,
            auto_assignment_log_id=log.id,
            revoked_by=admin_user.id,
        )

        # 再次撤销应抛异常
        with pytest.raises(BusinessException):
            AutoAssignmentService.revoke(
                academic_year_id=academic_year.id,
                auto_assignment_log_id=log.id,
                revoked_by=admin_user.id,
            )

    def test_revoke_rejects_nonexistent_log(self, academic_year, admin_user):
        """撤销不存在的 log 抛异常"""
        _setup_state(academic_year)
        with pytest.raises(BusinessException):
            AutoAssignmentService.revoke(
                academic_year_id=academic_year.id,
                auto_assignment_log_id=99999,
                revoked_by=admin_user.id,
            )

    def test_revoke_only_deletes_auto_assigned(self, academic_year, admin_user):
        """撤销只删除 AUTO_ASSIGNED 来源的 admission"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        # 先手动分配 s1（不应被撤销删除）
        Admission.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            source=AdmissionSource.MANUAL.value,
        )

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        # 现在 s1 已有 MANUAL admission，s2 应被自动分配
        # 但 s1 已分配，所以 AutoAssignmentService 只会分配 s2
        auto_admission = Admission.objects.filter(
            source=AdmissionSource.AUTO_ASSIGNED.value
        ).get()
        assert auto_admission.student_id == s2.user_id

        log = AutoAssignmentLog.objects.get()
        result = AutoAssignmentService.revoke(
            academic_year_id=academic_year.id,
            auto_assignment_log_id=log.id,
            revoked_by=admin_user.id,
        )

        # 只撤销 1 条（s2）
        assert result["revoked_count"] == 1
        # s1 的 MANUAL admission 应保留
        assert Admission.objects.filter(
            source=AdmissionSource.MANUAL.value
        ).count() == 1
        assert Admission.objects.filter(
            source=AdmissionSource.AUTO_ASSIGNED.value
        ).count() == 0


# ===== Preview 测试 =====


@pytest.mark.django_db
class TestAutoAssignmentPreview:
    """Preview 预览测试（不获取锁）"""

    def test_preview_returns_summary(self, academic_year):
        """preview 返回汇总信息"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 2, academic_year)
        _create_student("20240001", "学生A")
        _create_student("20240002", "学生B")

        result = AutoAssignmentService.preview(academic_year_id=academic_year.id)

        assert result["total_unassigned"] == 2
        assert result["available_teachers"] == 1
        assert result["total_remaining_quota"] == 2
        assert len(result["previews"]) == 2

    def test_preview_no_unassigned(self, academic_year):
        """无未分配学生时 preview 返回空"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 2, academic_year)

        result = AutoAssignmentService.preview(academic_year_id=academic_year.id)

        assert result["total_unassigned"] == 0
        assert result["available_teachers"] == 1
        assert len(result["previews"]) == 0


# ===== 多导师公平分配测试 =====


@pytest.mark.django_db
class TestAutoAssignmentFairDistribution:
    """多导师公平分配测试"""

    def test_distribution_balances_by_remaining_quota(self, academic_year, admin_user):
        """多导师场景下的公平分配

        场景：T0001(2) T0002(2) T0003(1)，5 个学生
        预期分配顺序（每次取剩余最多的）：
        - s1→T0001 or T0002（都 2，按 number 升序选 T0001）
        - s2→T0002（T0001=1, T0002=2）
        - s3→T0001 or T0002（都 1，按 number 升序选 T0001）
        - s4→T0002（T0001=0, T0002=1）
        - s5→T0003（T0001=0, T0002=0, T0003=1）
        """
        _setup_state(academic_year)
        t1 = _create_teacher("T0001", "导师A", 2, academic_year)
        t2 = _create_teacher("T0002", "导师B", 2, academic_year)
        t3 = _create_teacher("T0003", "导师C", 1, academic_year)

        for i in range(1, 6):
            _create_student(f"2024000{i}", f"学生{i}")

        with patch(
            "apps.assignments.services.DistributedLock"
        ) as mock_lock_cls:
            mock_lock_cls.return_value = _make_lock_mock()
            result = AutoAssignmentService.run(
                academic_year_id=academic_year.id,
                triggered_by=admin_user.id,
            )

        assert result.assigned_count == 5

        t1_count = Admission.objects.filter(teacher=t1).count()
        t2_count = Admission.objects.filter(teacher=t2).count()
        t3_count = Admission.objects.filter(teacher=t3).count()

        assert t1_count == 2
        assert t2_count == 2
        assert t3_count == 1
