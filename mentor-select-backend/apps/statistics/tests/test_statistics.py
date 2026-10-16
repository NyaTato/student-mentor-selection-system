"""统计 API 测试

覆盖：
- Dashboard 统计：学生总数、导师总数、申请总数、录取总数、未分配学生数
- 申请统计：按状态/轮次/导师分组
- 录取统计：按来源/导师分组
- 导师名额统计：max_quota / admitted / remaining / utilization
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.assignments.models import Admission, AutoAssignmentLog
from apps.common.enums import (
    AcademicYearStatus,
    AdmissionSource,
    ApplicationRound,
    ApplicationStatus,
    AutoAssignmentStatus,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.applications.models import Application
from apps.students.models import StudentProfile
from apps.system.models import SystemState
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import User
from apps.statistics.services import StatisticsService


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


@pytest.mark.django_db
class TestDashboardStatistics:
    """Dashboard 统计测试"""

    def test_dashboard_empty(self, academic_year):
        """空数据 Dashboard"""
        _setup_state(academic_year)
        service = StatisticsService()
        result = service.get_dashboard(academic_year.id)

        assert result["academic_year_id"] == academic_year.id
        assert result["total_students"] == 0
        assert result["total_teachers"] == 0
        assert result["total_applications"] == 0
        assert result["total_admissions"] == 0
        assert result["unassigned_students"] == 0
        assert result["current_state"] == SystemStateValue.AUTO_ASSIGN.value

    def test_dashboard_with_data(self, academic_year):
        """有数据的 Dashboard"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")
        s3 = _create_student("20240003", "学生C")

        # 创建 1 个申请
        Application.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.APPROVED.value,
        )

        # 创建 1 个 admission（s1 已录取）
        Admission.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            source=AdmissionSource.MANUAL.value,
        )

        service = StatisticsService()
        result = service.get_dashboard(academic_year.id)

        assert result["total_students"] == 3
        assert result["total_teachers"] == 1
        assert result["total_applications"] == 1
        assert result["total_admissions"] == 1
        assert result["unassigned_students"] == 2  # s2, s3 未录取
        assert "已通过" in result["applications_by_status"]
        assert "人工分配" in result["admissions_by_source"]


@pytest.mark.django_db
class TestApplicationStatistics:
    """申请统计测试"""

    def test_applications_by_status(self, academic_year):
        """按状态分组的申请统计"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 5, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        Application.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.APPROVED.value,
        )
        Application.objects.create(
            academic_year=academic_year,
            student=s2,
            teacher=teacher,
            round=ApplicationRound.FIRST_ROUND.value,
            status=ApplicationStatus.PENDING.value,
        )

        service = StatisticsService()
        result = service.get_applications_statistics(academic_year.id)

        assert result["total"] == 2
        assert result["by_status"]["已通过"] == 1
        assert result["by_status"]["待处理"] == 1

    def test_applications_by_teacher(self, academic_year):
        """按导师分组的申请统计"""
        _setup_state(academic_year)
        t1 = _create_teacher("T0001", "导师A", 5, academic_year)
        t2 = _create_teacher("T0002", "导师B", 5, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")
        s3 = _create_student("20240003", "学生C")

        for s, t in [(s1, t1), (s2, t1), (s3, t2)]:
            Application.objects.create(
                academic_year=academic_year,
                student=s,
                teacher=t,
                round=ApplicationRound.FIRST_ROUND.value,
                status=ApplicationStatus.PENDING.value,
            )

        service = StatisticsService()
        result = service.get_applications_statistics(academic_year.id)

        assert result["total"] == 3
        # t1 应有 2 个，t2 应有 1 个
        assert result["by_teacher"][0]["count"] == 2
        assert result["by_teacher"][1]["count"] == 1


@pytest.mark.django_db
class TestAdmissionStatistics:
    """录取统计测试"""

    def test_admissions_by_source(self, academic_year):
        """按来源分组的录取统计"""
        _setup_state(academic_year)
        teacher = _create_teacher("T0001", "导师A", 5, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        Admission.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=teacher,
            source=AdmissionSource.MANUAL.value,
        )
        Admission.objects.create(
            academic_year=academic_year,
            student=s2,
            teacher=teacher,
            source=AdmissionSource.AUTO_ASSIGNED.value,
        )

        service = StatisticsService()
        result = service.get_admissions_statistics(academic_year.id)

        assert result["total"] == 2
        assert result["by_source"]["人工分配"] == 1
        assert result["by_source"]["自动分配"] == 1

    def test_admissions_by_teacher(self, academic_year):
        """按导师分组的录取统计（含名额信息）"""
        _setup_state(academic_year)
        t1 = _create_teacher("T0001", "导师A", 3, academic_year)
        t2 = _create_teacher("T0002", "导师B", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")
        s3 = _create_student("20240003", "学生C")

        for s, t in [(s1, t1), (s2, t1), (s3, t2)]:
            Admission.objects.create(
                academic_year=academic_year,
                student=s,
                teacher=t,
                source=AdmissionSource.MANUAL.value,
            )

        service = StatisticsService()
        result = service.get_admissions_statistics(academic_year.id)

        assert result["total"] == 3
        # t1 应有 2 个录取
        t1_item = next(t for t in result["by_teacher"] if t["teacher_id"] == t1.user_id)
        assert t1_item["count"] == 2
        assert t1_item["max_quota"] == 3
        assert t1_item["remaining"] == 1


@pytest.mark.django_db
class TestTeacherQuotaStatistics:
    """导师名额使用情况统计测试"""

    def test_quota_statistics(self, academic_year):
        """导师名额使用情况"""
        _setup_state(academic_year)
        t1 = _create_teacher("T0001", "导师A", 3, academic_year)
        t2 = _create_teacher("T0002", "导师B", 2, academic_year)
        s1 = _create_student("20240001", "学生A")
        s2 = _create_student("20240002", "学生B")

        Admission.objects.create(
            academic_year=academic_year,
            student=s1,
            teacher=t1,
            source=AdmissionSource.MANUAL.value,
        )
        Admission.objects.create(
            academic_year=academic_year,
            student=s2,
            teacher=t2,
            source=AdmissionSource.MANUAL.value,
        )

        service = StatisticsService()
        result = service.get_teachers_quota_statistics(academic_year.id)

        assert result["total_teachers"] == 2
        assert result["total_quota"] == 5
        assert result["total_admitted"] == 2
        assert result["total_remaining"] == 3

        # 验证利用率
        t1_item = next(t for t in result["teachers"] if t["teacher_id"] == t1.user_id)
        assert t1_item["admitted"] == 1
        assert t1_item["remaining"] == 2
        assert t1_item["utilization"] == round(1 / 3 * 100, 2)

    def test_quota_statistics_empty(self, academic_year):
        """无导师名额配置"""
        _setup_state(academic_year)
        service = StatisticsService()
        result = service.get_teachers_quota_statistics(academic_year.id)

        assert result["total_teachers"] == 0
        assert result["total_quota"] == 0
        assert result["total_admitted"] == 0
        assert result["total_remaining"] == 0
        assert len(result["teachers"]) == 0


@pytest.mark.django_db
class TestStatisticsAPI:
    """统计 API 端点测试"""

    def test_dashboard_api_requires_academic_year(self, authenticated_client):
        """Dashboard API 缺少 academic_year 参数返回错误"""
        resp = authenticated_client.get("/api/v1/statistics/dashboard/")
        assert resp.status_code in (200, 400)
        data = resp.json()
        assert data["code"] != 0  # 错误响应

    def test_dashboard_api_success(self, authenticated_client, academic_year):
        """Dashboard API 成功响应"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 2, academic_year)
        _create_student("20240001", "学生A")

        resp = authenticated_client.get(
            f"/api/v1/statistics/dashboard/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total_students"] == 1
        assert data["data"]["total_teachers"] == 1

    def test_applications_api(self, authenticated_client, academic_year):
        """申请统计 API"""
        _setup_state(academic_year)
        resp = authenticated_client.get(
            f"/api/v1/statistics/applications/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    def test_admissions_api(self, authenticated_client, academic_year):
        """录取统计 API"""
        _setup_state(academic_year)
        resp = authenticated_client.get(
            f"/api/v1/statistics/admissions/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_teachers_api(self, authenticated_client, academic_year):
        """导师名额统计 API"""
        _setup_state(academic_year)
        _create_teacher("T0001", "导师A", 2, academic_year)

        resp = authenticated_client.get(
            f"/api/v1/statistics/teachers/?academic_year={academic_year.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total_teachers"] == 1

    def test_dashboard_api_forbidden_for_student(self, student_client, academic_year):
        """Dashboard API 对学生用户禁止访问"""
        resp = student_client.get(
            f"/api/v1/statistics/dashboard/?academic_year={academic_year.id}"
        )
        assert resp.status_code in (401, 403)
