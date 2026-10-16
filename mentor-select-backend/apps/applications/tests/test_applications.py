"""
申请模块测试
覆盖 Model / Serializer / Service / Permission / Business Rules
"""
import pytest
from django.utils import timezone

from apps.applications.models import Application
from apps.applications.services import ApplicationService
from apps.common.enums import (
    ApplicationRound,
    ApplicationStatus,
    SystemStateValue,
    UserRole,
)
from apps.common.exceptions import (
    BusinessException,
    NotFoundError,
    StateTransitionError,
)
from apps.system.models import SystemState
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import User


def _make_quota(academic_year, teacher_profile, max_quota):
    """为导师配置本学年名额

    业务契约（Task 02 有意变更）：**未配置名额 = 不允许录取/占位**。
    只有真正会发生「录取 / 占用名额」的用例才需要调用本 helper；
    未配置名额的拒绝行为由 test_v2_business.py 的两个 _without_quota 用例覆盖。
    """
    return TeacherQuota.objects.create(
        academic_year=academic_year,
        teacher=teacher_profile,
        max_quota=max_quota,
    )


@pytest.mark.django_db
class TestApplicationModel:
    """Application Model 测试"""

    def test_create_application(
        self, academic_year, student_profile, teacher_profile
    ):
        app = Application.objects.create(
            academic_year=academic_year,
            student=student_profile,
            teacher=teacher_profile,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.PENDING.value,
        )
        assert app.id is not None
        assert app.round == ApplicationRound.FIRST_ROUND.value
        assert app.status == ApplicationStatus.PENDING.value

    def test_unique_year_student_round(
        self, academic_year, student_profile, teacher_profile
    ):
        """同学年同学生同轮次唯一"""
        Application.objects.create(
            academic_year=academic_year,
            student=student_profile,
            teacher=teacher_profile,
            round=ApplicationRound.FIRST_ROUND.value,
        )
        with pytest.raises(Exception):  # IntegrityError
            Application.objects.create(
                academic_year=academic_year,
                student=student_profile,
                teacher=teacher_profile,
                round=ApplicationRound.FIRST_ROUND.value,
            )

    def test_str_representation(
        self, academic_year, student_profile, teacher_profile
    ):
        app = Application.objects.create(
            academic_year=academic_year,
            student=student_profile,
            teacher=teacher_profile,
            round=ApplicationRound.FIRST_ROUND.value,
        )
        assert "student" in str(app)
        assert "teacher" in str(app)


@pytest.mark.django_db
class TestApplicationServiceSubmit:
    """申请提交业务测试"""

    def _init_state(self, academic_year, state_value):
        """初始化系统状态到指定值"""
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=state_value,
            state_changed_at=timezone.now(),
        )

    def test_submit_first_round_success(
        self, academic_year, student_profile, teacher_profile
    ):
        """第一轮申请提交成功"""
        self._init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        service = ApplicationService()
        app = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.FIRST_ROUND.value,
        })
        assert app.id is not None
        assert app.status == ApplicationStatus.PENDING.value

    def test_submit_first_round_wrong_state(
        self, academic_year, student_profile, teacher_profile
    ):
        """系统状态不对时第一轮申请失败"""
        self._init_state(academic_year, SystemStateValue.INIT.value)
        service = ApplicationService()
        with pytest.raises(StateTransitionError):
            service.create({
                "academic_year": academic_year,
                "student": student_profile,
                "teacher": teacher_profile,
                "round": ApplicationRound.FIRST_ROUND.value,
            })

    def test_submit_duplicate_round(
        self, academic_year, student_profile, teacher_profile
    ):
        """第一轮 PENDING 状态重复提交 = **修改导师**（同一行，不新增申请）

        业务要求（用户确认）：第一轮审核前允许改选导师，
        必须复用原申请行并保持 PENDING，而不是拒绝、也不是插入第二条。
        """
        other_teacher_user = User.objects.create_user(
            username="teacher002",
            password="TestPass123!",
            role=UserRole.TEACHER.value,
        )
        other_teacher = TeacherProfile.objects.create(
            user=other_teacher_user,
            teacher_number="T0002",
            name="导师二",
            college="计算机学院",
        )

        self._init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        service = ApplicationService()
        first = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.FIRST_ROUND.value,
        })

        updated = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": other_teacher,
            "round": ApplicationRound.FIRST_ROUND.value,
        })

        rows = Application.objects.filter(
            academic_year=academic_year,
            student=student_profile,
            round=ApplicationRound.FIRST_ROUND.value,
        )
        assert rows.count() == 1  # 仍然只有一行
        assert updated.id == first.id  # 复用同一申请行
        assert rows.first().teacher_id == other_teacher.user_id  # 导师已更新
        assert updated.status == ApplicationStatus.PENDING.value

    def test_submit_first_round_after_rejected_is_denied(
        self, academic_year, student_profile, teacher_profile
    ):
        """已审核（REJECTED）的第一轮申请不可再修改

        只有 PENDING 才允许改选导师；已处理申请再提交必须被拒绝，
        且不得改动任何行。
        """
        self._init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        service = ApplicationService()
        first = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.FIRST_ROUND.value,
        })
        first.status = ApplicationStatus.REJECTED.value
        first.save(update_fields=["status"])

        with pytest.raises(BusinessException) as exc:
            service.create({
                "academic_year": academic_year,
                "student": student_profile,
                "teacher": teacher_profile,
                "round": ApplicationRound.FIRST_ROUND.value,
            })
        assert "已被审核" in str(exc.value.detail)

        rows = Application.objects.filter(
            academic_year=academic_year,
            student=student_profile,
            round=ApplicationRound.FIRST_ROUND.value,
        )
        assert rows.count() == 1
        assert rows.first().status == ApplicationStatus.REJECTED.value

    def test_submit_second_round_without_first(
        self, academic_year, student_profile, teacher_profile
    ):
        """第二轮申请前必须提交第一轮"""
        self._init_state(academic_year, SystemStateValue.SECOND_ROUND_OPEN.value)
        service = ApplicationService()
        with pytest.raises(BusinessException):
            service.create({
                "academic_year": academic_year,
                "student": student_profile,
                "teacher": teacher_profile,
                "round": ApplicationRound.SECOND_ROUND.value,
            })

    def test_submit_second_round_after_first_approved(
        self, academic_year, student_profile, teacher_profile
    ):
        """第一轮已通过，不能提交第二轮"""
        self._init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        service = ApplicationService()
        # 提交第一轮
        app = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.FIRST_ROUND.value,
        })
        # 直接修改状态为已通过
        app.status = ApplicationStatus.APPROVED.value
        app.save(update_fields=["status"])

        # 切换到第二轮状态
        state = SystemState.objects.get(academic_year_id=academic_year.id)
        state.current_state = SystemStateValue.SECOND_ROUND_OPEN.value
        state.save(update_fields=["current_state"])

        with pytest.raises(BusinessException):
            service.create({
                "academic_year": academic_year,
                "student": student_profile,
                "teacher": teacher_profile,
                "round": ApplicationRound.SECOND_ROUND.value,
            })

    def test_submit_second_round_after_first_rejected(
        self, academic_year, student_profile, teacher_profile
    ):
        """第一轮被拒绝后，可以提交第二轮"""
        self._init_state(academic_year, SystemStateValue.FIRST_ROUND_OPEN.value)
        service = ApplicationService()
        # 提交第一轮
        app = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.FIRST_ROUND.value,
        })
        # 直接修改状态为已拒绝
        app.status = ApplicationStatus.REJECTED.value
        app.save(update_fields=["status"])

        # 切换到第二轮状态
        state = SystemState.objects.get(academic_year_id=academic_year.id)
        state.current_state = SystemStateValue.SECOND_ROUND_OPEN.value
        state.save(update_fields=["current_state"])

        # 第二轮申请即占用名额：必须先配置名额（未配置 = 拒绝）
        _make_quota(academic_year, teacher_profile, max_quota=1)

        # 提交第二轮
        app2 = service.create({
            "academic_year": academic_year,
            "student": student_profile,
            "teacher": teacher_profile,
            "round": ApplicationRound.SECOND_ROUND.value,
        })
        assert app2.id is not None
        assert app2.round == ApplicationRound.SECOND_ROUND.value


@pytest.mark.django_db
class TestApplicationServiceReview:
    """申请审核业务测试"""

    def _init_state(self, academic_year, state_value):
        SystemState.objects.create(
            academic_year=academic_year,
            current_state=state_value,
            state_changed_at=timezone.now(),
        )

    def _create_pending_app(
        self, academic_year, student_profile, teacher_profile, round_value
    ):
        return Application.objects.create(
            academic_year=academic_year,
            student=student_profile,
            teacher=teacher_profile,
            round=round_value,
            status=ApplicationStatus.PENDING.value,
        )

    def test_approve_first_round(
        self, academic_year, student_profile, teacher_profile, teacher_user
    ):
        """导师通过第一轮申请"""
        self._init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        _make_quota(academic_year, teacher_profile, max_quota=1)
        app = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        result = service.approve(app.id, teacher_user)
        assert result.status == ApplicationStatus.APPROVED.value
        from apps.assignments.models import Admission

        admission = Admission.objects.get(
            academic_year=academic_year, student=student_profile
        )
        assert admission.teacher_id == teacher_profile.user_id

    def test_reject_first_round(
        self, academic_year, student_profile, teacher_profile, teacher_user
    ):
        """导师拒绝第一轮申请"""
        self._init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        result = service.reject(app.id, teacher_user)
        assert result.status == ApplicationStatus.REJECTED.value

    def test_approve_wrong_state(
        self, academic_year, student_profile, teacher_profile, teacher_user
    ):
        """系统状态不对时审核失败"""
        self._init_state(academic_year, SystemStateValue.INIT.value)
        app = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        with pytest.raises(StateTransitionError):
            service.approve(app.id, teacher_user)

    def test_approve_already_processed(
        self, academic_year, student_profile, teacher_profile, teacher_user
    ):
        """已处理的申请不能重复操作"""
        self._init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        _make_quota(academic_year, teacher_profile, max_quota=1)
        app = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        service.approve(app.id, teacher_user)
        with pytest.raises(BusinessException):
            service.approve(app.id, teacher_user)

    def test_approve_not_found(self, teacher_user):
        service = ApplicationService()
        with pytest.raises(NotFoundError):
            service.approve(99999, teacher_user)

    def test_approve_by_student_forbidden(
        self, academic_year, student_profile, teacher_profile, student_user
    ):
        """学生不能审核申请"""
        self._init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        app = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        with pytest.raises(BusinessException):
            service.approve(app.id, student_user)

    def test_batch_approve(
        self, academic_year, student_profile, teacher_profile, teacher_user
    ):
        """批量通过"""
        self._init_state(academic_year, SystemStateValue.TEACHER_REVIEW.value)
        # 创建第二个学生
        user2 = User.objects.create_user(
            username="student002",
            password="TestPass123!",
            role=UserRole.STUDENT.value,
        )
        from apps.students.models import StudentProfile

        student2 = StudentProfile.objects.create(
            user=user2,
            student_number="20240002",
            name="学生二",
            major="计算机",
            class_name="计科2402",
        )
        app1 = self._create_pending_app(
            academic_year, student_profile, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        app2 = self._create_pending_app(
            academic_year, student2, teacher_profile,
            ApplicationRound.FIRST_ROUND.value,
        )
        service = ApplicationService()
        _make_quota(academic_year, teacher_profile, max_quota=2)
        result = service.batch_approve([app1.id, app2.id], teacher_user)
        assert len(result) == 2
        from apps.assignments.models import Admission

        assert Admission.objects.filter(academic_year=academic_year).count() == 2


@pytest.mark.django_db
class TestApplicationPermission:
    """申请权限测试"""

    def test_admin_can_list_applications(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/applications/")
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get("/api/v1/applications/")
        assert resp.status_code == 401

    def test_student_can_list_own(self, student_client):
        """学生可以查看自己的申请"""
        resp = student_client.get("/api/v1/applications/")
        assert resp.status_code == 200

    def test_teacher_can_list_received(self, teacher_client):
        """导师可以查看收到的申请"""
        resp = teacher_client.get("/api/v1/applications/")
        assert resp.status_code == 200
