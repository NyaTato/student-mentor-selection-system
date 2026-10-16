"""v2 业务闭环测试

覆盖 Task 02 要求的关键行为：
1. v1 / v2 读取同一份状态（同一批 View 的兼容别名）
2. 越权角色访问被拒
3. 第一轮：修改 + 审核通过 + 审核拒绝
4. 第二轮：立即录取 / 取消 / 重新申请 / 名额已满 / 未配置名额
5. 人工分配：持久化 / 重复 / 名额已满 / 阶段限制 / 权限
6. 撤销：学年不匹配
7. 公告：未发布对非管理员不可见（即使显式请求 is_published=false）
8. imports / logs：仅管理员
9. 名额：不得低于已录取人数

注意：本模块只能由 Codex 在项目环境中运行验证；作者侧未执行（无 shell 权限）。
"""
from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academic_year.models import AcademicYear
from apps.announcements.models import Announcement
from apps.applications.models import Application
from apps.assignments.models import Admission, AutoAssignmentLog
from apps.common.enums import (
    AdmissionSource,
    ApplicationRound,
    ApplicationStatus,
    AutoAssignmentStatus,
    SystemStateValue,
    UserRole,
)
from apps.system.models import SystemState
from apps.teachers.models import TeacherQuota

pytestmark = pytest.mark.django_db


# ===== 本地工厂 =====


def make_year(name="2025-2026", status=1):
    return AcademicYear.objects.create(name=name, start_year=2025, end_year=2026, status=status)


def make_state(year, state):
    return SystemState.objects.create(
        academic_year=year,
        current_state=state,
        previous_state=state,
        state_changed_at=timezone.now(),
    )


def make_quota(year, teacher_user, max_quota):
    return TeacherQuota.objects.create(
        academic_year=year, teacher_id=teacher_user.id, max_quota=max_quota
    )


def make_application(year, student_user, teacher_user, round_value, status):
    return Application.objects.create(
        academic_year=year,
        student_id=student_user.id,
        teacher_id=teacher_user.id,
        round=round_value,
        status=status,
    )


def make_admission(year, student_user, teacher_user, source=AdmissionSource.ADMIT_ROUND1.value,
                   application=None, log=None):
    return Admission.objects.create(
        academic_year=year,
        student_id=student_user.id,
        teacher_id=teacher_user.id,
        source=source,
        application=application,
        auto_assignment_log=log,
    )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def error_code(response):
    try:
        return response.json().get("code")
    except Exception:  # pragma: no cover - 非 JSON 响应
        return None


# ===== 1. v1 / v2 读取一致（兼容适配层）=====


def test_v1_and_v2_share_same_state(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """v1 与 v2 指向同一份实现/数据：同一请求返回同一录取结果。

    两条 URL 由同一个 View 类提供（v1 兼容别名），因此必须返回同一批 id，
    不允许「路由不存在」的静默跳过。
    """
    year = make_year()
    admission = make_admission(year, api_student_user, api_teacher_user)

    client = client_for(api_student_user)
    v2 = client.get(f"/api/v2/assignments/admissions/?academic_year={year.id}")
    v1 = client.get(f"/api/v1/assignments/admissions/?academic_year={year.id}")

    assert v2.status_code == 200, v2.content
    assert v1.status_code == 200, v1.content

    # 分页响应：data 为 {list, total, page, page_size, total_pages}
    v2_ids = {row["id"] for row in v2.json()["data"]["list"]}
    v1_ids = {row["id"] for row in v1.json()["data"]["list"]}
    assert admission.id in v2_ids
    assert v2_ids == v1_ids
    assert v2.json()["data"]["total"] == v1.json()["data"]["total"] == 1


# ===== 2. 越权 =====


def test_student_cannot_read_other_students_admission(
    api_student_user, api_teacher_user, api_teacher_profile, api_admin_user
):
    """学生列表接口必须裁剪到自身，不能请求他人数据。"""
    from apps.students.models import StudentProfile
    from apps.users.models import User

    other = User.objects.create_user(
        username="other_stu", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=other, student_number="S20240001", name="他人", major="计算机科学", class_name="X"
    )

    year = make_year()
    make_admission(year, other, api_teacher_user)

    resp = client_for(api_student_user).get(
        f"/api/v2/assignments/admissions/?academic_year={year.id}"
    )
    assert resp.status_code == 200
    # 分页响应：学生只能看到自己名下（此处为空集）
    assert resp.json()["data"]["list"] == []
    assert resp.json()["data"]["total"] == 0
    assert Admission.objects.filter(academic_year=year, student_id=other.id).exists()


def test_non_admin_cannot_manual_assign(api_teacher_user, api_teacher_profile, api_student_user):
    """人工分配是管理员专属能力。"""
    year = make_year()
    make_state(year, SystemStateValue.AUTO_ASSIGN.value)

    resp = client_for(api_teacher_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code == 403


def test_imports_and_logs_are_admin_only():
    """导入任务/日志、操作日志/登录日志：权限类必须包含 IsAdmin。"""
    from apps.common.permissions import IsAdmin
    from apps.imports.views import ImportLogViewSet, ImportTaskViewSet
    from apps.logs.views import LoginLogViewSet, OperationLogViewSet

    for view in (ImportTaskViewSet, ImportLogViewSet):
        assert IsAdmin in view.permission_classes

    for view in (OperationLogViewSet, LoginLogViewSet):
        assert IsAdmin in view.permission_classes


# ===== 3. 第一轮：修改 / 通过 / 拒绝 =====


def test_first_round_can_modify_pending_application(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile, api_admin_user
):
    """第一轮 PENDING 状态下再次提交 = 修改导师（不新增第二条申请）。"""
    from apps.users.models import User
    from apps.teachers.models import TeacherProfile

    second = User.objects.create_user(
        username="t2", password="pass12345", role=UserRole.TEACHER.value, status=1
    )
    TeacherProfile.objects.create(user=second, teacher_number="T0002", name="导师二", college="计算机学院")

    year = make_year()
    make_state(year, SystemStateValue.FIRST_ROUND_OPEN.value)

    client = client_for(api_student_user)
    payload = {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 1}
    assert client.post("/api/v2/applications/", payload, format="json").status_code == 201

    payload["teacher"] = second.id
    resp = client.post("/api/v2/applications/", payload, format="json")
    assert resp.status_code in (200, 201)

    apps = Application.objects.filter(
        academic_year=year, student_id=api_student_user.id, round=1
    )
    assert apps.count() == 1
    assert apps.first().teacher_id == second.id
    assert apps.first().status == ApplicationStatus.PENDING.value


def test_first_round_approve_creates_admission(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.PENDING.value,
    )

    resp = client_for(api_teacher_user).post(f"/api/v2/applications/{app.id}/approve/", {}, format="json")
    assert resp.status_code == 200

    app.refresh_from_db()
    assert app.status == ApplicationStatus.APPROVED.value
    admission = Admission.objects.get(academic_year=year, student_id=api_student_user.id)
    assert admission.teacher_id == api_teacher_user.id
    assert admission.source == AdmissionSource.ADMIT_ROUND1.value


def test_first_round_approve_without_quota_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """行为变更：未配置名额 = 不允许录取（原先会跳过名额校验）。"""
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.PENDING.value,
    )

    resp = client_for(api_teacher_user).post(f"/api/v2/applications/{app.id}/approve/", {}, format="json")
    assert resp.status_code >= 400
    assert error_code(resp) == 40003  # QUOTA_NOT_FOUND
    assert not Admission.objects.filter(academic_year=year).exists()


def test_first_round_reject(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.PENDING.value,
    )

    resp = client_for(api_teacher_user).post(f"/api/v2/applications/{app.id}/reject/", {}, format="json")
    assert resp.status_code == 200
    app.refresh_from_db()
    assert app.status == ApplicationStatus.REJECTED.value


def test_teacher_cannot_review_another_teachers_application(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    from apps.teachers.models import TeacherProfile
    from apps.users.models import User

    other = User.objects.create_user(
        username="t3", password="pass12345", role=UserRole.TEACHER.value, status=1
    )
    TeacherProfile.objects.create(user=other, teacher_number="T0003", name="导师三", college="计算机学院")

    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 1)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.PENDING.value,
    )

    resp = client_for(other).post(f"/api/v2/applications/{app.id}/approve/", {}, format="json")
    assert resp.status_code >= 400
    assert error_code(resp) == 12001  # PERMISSION_DENIED


# ===== 4. 第二轮 =====


def test_second_round_immediate_admission_cancel_reapply(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """第二轮：申请即录取 -> 取消释放名额 -> 可重新申请。"""
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 1)
    make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.REJECTED.value,
    )

    client = client_for(api_student_user)
    payload = {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2}

    resp = client.post("/api/v2/applications/", payload, format="json")
    assert resp.status_code in (200, 201)
    app = Application.objects.get(academic_year=year, student_id=api_student_user.id, round=2)
    assert app.status == ApplicationStatus.APPROVED.value
    assert Admission.objects.filter(academic_year=year, application=app).count() == 1

    # 名额已满 -> 再次申请（同轮次）被拒
    resp = client.post("/api/v2/applications/", payload, format="json")
    assert resp.status_code >= 400

    # 取消 -> 释放名额
    cancel = client.post(f"/api/v2/applications/{app.id}/cancel/", {}, format="json")
    assert cancel.status_code == 200
    assert not Admission.objects.filter(academic_year=year).exists()
    assert not Application.objects.filter(id=app.id).exists()

    # 重新申请成功
    resp = client.post("/api/v2/applications/", payload, format="json")
    assert resp.status_code in (200, 201)
    assert Admission.objects.filter(academic_year=year).count() == 1


def test_second_round_cancel_does_not_delete_unrelated_manual_admission(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """取消第二轮申请绝不能按「学生」删除，必须精确匹配该申请关联的录取。"""
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 5)

    # 人工分配产生的录取（与该申请无关）
    manual = make_admission(
        year, api_student_user, api_teacher_user, source=AdmissionSource.MANUAL.value
    )
    # 另一名学生的第二轮录取（也不应被删除）
    from apps.students.models import StudentProfile
    from apps.users.models import User

    other = User.objects.create_user(
        username="stu_x", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=other, student_number="S20240002", name="另一", major="计算机科学", class_name="Y"
    )
    other_admission = make_admission(
        year, other, api_teacher_user, source=AdmissionSource.ADMIT_ROUND2.value
    )

    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.SECOND_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    # 注意：同一学年同一学生只能有一条 admission（uk_year_student），
    # 因此这里直接复用 manual 记录并通过 application 关联，验证「精确匹配」语义。
    manual.application = app
    manual.source = AdmissionSource.ADMIT_ROUND2.value
    manual.save()

    cancel = client_for(api_student_user).post(
        f"/api/v2/applications/{app.id}/cancel/", {}, format="json"
    )
    assert cancel.status_code == 200
    assert not Admission.objects.filter(id=manual.id).exists()
    assert Admission.objects.filter(id=other_admission.id).exists()


def test_second_round_requires_rejected_first_round(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 1)

    resp = client_for(api_student_user).post(
        "/api/v2/applications/",
        {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2},
        format="json",
    )
    assert resp.status_code >= 400


def test_second_round_without_quota_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.REJECTED.value,
    )

    resp = client_for(api_student_user).post(
        "/api/v2/applications/",
        {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2},
        format="json",
    )
    assert resp.status_code >= 400
    assert error_code(resp) == 40003  # QUOTA_NOT_FOUND


def test_second_round_full_quota_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    from apps.students.models import StudentProfile
    from apps.users.models import User

    occupant = User.objects.create_user(
        username="stu_occ", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=occupant, student_number="S20240003", name="占位", major="计算机科学", class_name="Z"
    )

    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 1)
    make_admission(year, occupant, api_teacher_user, source=AdmissionSource.ADMIT_ROUND2.value)
    make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.REJECTED.value,
    )

    resp = client_for(api_student_user).post(
        "/api/v2/applications/",
        {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2},
        format="json",
    )
    assert resp.status_code >= 400
    assert error_code(resp) == 60003  # ADMISSION_QUOTA_FULL


def test_second_round_open_requires_correct_system_state(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 1)
    make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.REJECTED.value,
    )

    resp = client_for(api_student_user).post(
        "/api/v2/applications/",
        {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2},
        format="json",
    )
    assert resp.status_code >= 400


# ===== 5. 人工分配 =====


def test_manual_assign_persists(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.AUTO_ASSIGN.value)
    make_quota(year, api_teacher_user, 2)

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code == 201
    admission = Admission.objects.get(academic_year=year, student_id=api_student_user.id)
    assert admission.source == AdmissionSource.MANUAL.value
    assert admission.teacher_id == api_teacher_user.id
    assert resp.json()["data"]["id"] == admission.id


def test_manual_assign_duplicate_is_denied(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.FINISHED.value)
    make_quota(year, api_teacher_user, 2)
    make_admission(year, api_student_user, api_teacher_user, source=AdmissionSource.MANUAL.value)

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code >= 400
    assert error_code(resp) == 60002  # ADMISSION_EXISTS


def test_manual_assign_full_quota_is_denied(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    from apps.students.models import StudentProfile
    from apps.users.models import User

    occupant = User.objects.create_user(
        username="stu_occ2", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=occupant, student_number="S20240004", name="占位2", major="计算机科学", class_name="Z"
    )

    year = make_year()
    make_state(year, SystemStateValue.AUTO_ASSIGN.value)
    make_quota(year, api_teacher_user, 1)
    make_admission(year, occupant, api_teacher_user, source=AdmissionSource.MANUAL.value)

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code >= 400
    assert error_code(resp) == 60003  # ADMISSION_QUOTA_FULL


def test_manual_assign_wrong_phase_is_denied(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.FIRST_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 1)

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code >= 400


def test_manual_assign_invalid_payload_returns_400(
    api_admin_user, api_admin_profile, api_teacher_user, api_teacher_profile
):
    """Serializer 负责类型校验：非法输入 -> 400（而不是 500）。"""
    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": "abc", "student": None, "teacher": 1},
        format="json",
    )
    assert resp.status_code == 400


def test_manual_assign_rejects_disabled_participant(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_state(year, SystemStateValue.AUTO_ASSIGN.value)
    make_quota(year, api_teacher_user, 2)

    api_student_user.status = 2  # DISABLED
    api_student_user.save(update_fields=["status"])

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/manual-assign/",
        {"academic_year": year.id, "student": api_student_user.id, "teacher": api_teacher_user.id},
        format="json",
    )
    assert resp.status_code >= 400


# ===== 6. 撤销：学年不匹配 =====


def test_revoke_wrong_year_is_denied(
    api_admin_user, api_admin_profile, api_teacher_user, api_teacher_profile
):
    year_a = make_year(name="2025-2026")
    year_b = make_year(name="2026-2027", status=0)
    make_state(year_b, SystemStateValue.AUTO_ASSIGN.value)
    log = AutoAssignmentLog.objects.create(
        academic_year=year_a,
        status=AutoAssignmentStatus.SUCCESS.value,
        total_unassigned=1,
        assigned_count=1,
        failed_count=0,
        triggered_by=api_admin_user,
        started_at=timezone.now(),
    )

    resp = client_for(api_admin_user).post(
        "/api/v2/assignments/auto-assign/revoke/",
        {"academic_year": year_b.id, "auto_assignment_log": log.id},
        format="json",
    )
    assert resp.status_code >= 400
    log.refresh_from_db()
    assert log.is_revoked is False


# ===== 7. 公告可见性 =====


def test_unpublished_announcement_hidden_from_non_admin(
    api_student_user, api_student_profile
):
    year = make_year()
    Announcement.objects.create(
        academic_year=year, title="草稿公告", content="未发布", is_published=False,
        created_by=api_student_user,
    )
    Announcement.objects.create(
        academic_year=year, title="已发布公告", content="已发布", is_published=True,
        published_at=timezone.now(), created_by=api_student_user,
    )

    client = client_for(api_student_user)
    resp = client.get(f"/api/v2/announcements/?academic_year={year.id}")
    assert resp.status_code == 200
    titles = [row["title"] for row in resp.json()["data"]["list"]]
    assert "草稿公告" not in titles
    assert "已发布公告" in titles

    # 即使显式请求 is_published=false，非管理员也不得看到未发布公告
    resp = client.get(f"/api/v2/announcements/?academic_year={year.id}&is_published=false")
    assert resp.status_code == 200
    titles = [row["title"] for row in resp.json()["data"]["list"]]
    assert "草稿公告" not in titles
    assert "已发布公告" in titles


def test_admin_can_see_unpublished_announcement(
    api_admin_user, api_admin_profile
):
    year = make_year()
    Announcement.objects.create(
        academic_year=year, title="草稿公告", content="未发布", is_published=False,
        created_by=api_admin_user,
    )
    resp = client_for(api_admin_user).get(f"/api/v2/announcements/?academic_year={year.id}")
    assert resp.status_code == 200
    assert "草稿公告" in [row["title"] for row in resp.json()["data"]["list"]]


# ===== 7b. 布尔查询参数语义（QueryDict 归一化回归）=====


def test_announcement_is_published_filter_semantics(
    api_admin_user, api_admin_profile
):
    """缺省 is_published 必须「不过滤」，而不是被 HTML 表单语义当成 False。

    - 不传 is_published：管理员看到全部（含草稿）
    - is_published=true / false：显式过滤
    - is_published=abc：400（非法值不得被静默当成 False）
    """
    year = make_year()
    Announcement.objects.create(
        academic_year=year, title="草稿", content="c", is_published=False,
        created_by=api_admin_user,
    )
    Announcement.objects.create(
        academic_year=year, title="已发布", content="c", is_published=True,
        published_at=timezone.now(), created_by=api_admin_user,
    )

    client = client_for(api_admin_user)
    base = f"/api/v2/announcements/?academic_year={year.id}"

    resp = client.get(base)
    assert resp.status_code == 200
    assert {r["title"] for r in resp.json()["data"]["list"]} == {"草稿", "已发布"}

    resp = client.get(base + "&is_published=true")
    assert resp.status_code == 200
    assert [r["title"] for r in resp.json()["data"]["list"]] == ["已发布"]

    resp = client.get(base + "&is_published=false")
    assert resp.status_code == 200
    assert [r["title"] for r in resp.json()["data"]["list"]] == ["草稿"]

    resp = client.get(base + "&is_published=abc")
    assert resp.status_code == 400


def test_auto_log_is_revoked_filter_semantics(
    api_admin_user, api_admin_profile
):
    """自动分配日志的 is_revoked 缺省同样必须「不过滤」（同一归一化回归）。"""
    year = make_year()
    log = AutoAssignmentLog.objects.create(
        academic_year=year,
        status=AutoAssignmentStatus.SUCCESS.value,
        total_unassigned=1,
        assigned_count=1,
        failed_count=0,
        triggered_by=api_admin_user,
        started_at=timezone.now(),
        is_revoked=True,
    )

    client = client_for(api_admin_user)
    base = f"/api/v2/assignments/auto-logs/?academic_year={year.id}"

    resp = client.get(base)
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["data"]["list"]] == [log.id]

    resp = client.get(base + "&is_revoked=false")
    assert resp.status_code == 200
    assert resp.json()["data"]["list"] == []

    resp = client.get(base + "&is_revoked=true")
    assert resp.status_code == 200
    assert [r["id"] for r in resp.json()["data"]["list"]] == [log.id]

    resp = client.get(base + "&is_revoked=abc")
    assert resp.status_code == 400


# ===== 8. 名额不得低于已录取人数 =====


def test_quota_cannot_be_lowered_below_admitted(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    quota = make_quota(year, api_teacher_user, 2)
    make_admission(year, api_student_user, api_teacher_user)

    resp = client_for(api_admin_user).patch(
        f"/api/v2/teachers/quotas/{quota.id}/", {"max_quota": 0}, format="json"
    )
    assert resp.status_code >= 400
    assert error_code(resp) == 40004  # QUOTA_INVALID
    quota.refresh_from_db()
    assert quota.max_quota == 2


def test_quota_delete_denied_when_admitted(
    api_admin_user, api_admin_profile, api_student_user, api_student_profile,
    api_teacher_user, api_teacher_profile
):
    year = make_year()
    quota = make_quota(year, api_teacher_user, 2)
    make_admission(year, api_student_user, api_teacher_user)

    resp = client_for(api_admin_user).delete(f"/api/v2/teachers/quotas/{quota.id}/")
    assert resp.status_code >= 400
    assert TeacherQuota.objects.filter(id=quota.id, deleted_at__isnull=True).exists()


# ===== 9. 导师目录：汇总名额对已认证开放，写操作仍为管理员 =====


def test_teacher_directory_exposes_aggregate_quota_only(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    year = make_year()
    make_quota(year, api_teacher_user, 3)

    resp = client_for(api_student_user).get(
        f"/api/v2/teachers/profiles/directory/?academic_year={year.id}"
    )
    assert resp.status_code == 200
    row = next(
        r for r in resp.json()["data"] if r["teacher_id"] == api_teacher_user.id
    )
    assert row["max_quota"] == 3
    assert row["admitted_count"] == 0
    assert row["remaining_quota"] == 3
    # 不得包含学生明细字段
    assert "students" not in row and "student_ids" not in row


def test_teacher_directory_invalid_year_returns_400(
    api_student_user, api_student_profile
):
    resp = client_for(api_student_user).get(
        "/api/v2/teachers/profiles/directory/?academic_year=abc"
    )
    assert resp.status_code == 400


# ===== 10. 非法查询参数 -> 400（而非 500）=====


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/applications/?academic_year=abc",
        "/api/v2/assignments/admissions/?academic_year=abc",
        "/api/v2/assignments/auto-logs/?academic_year=abc",
    ],
)
def test_invalid_query_param_returns_400_not_500(
    path, api_admin_user, api_admin_profile
):
    resp = client_for(api_admin_user).get(path)
    assert resp.status_code == 400


# ===== 11. 撤销第一轮录取（POST applications/{id}/revoke-approval/）=====

REVOKE_V2 = "/api/v2/applications/{id}/revoke-approval/"
REVOKE_V1 = "/api/v1/applications/{id}/revoke-approval/"


def make_other_teacher(username: str, teacher_number: str, college: str = "计算机学院"):
    """创建另一名导师（canonical User + TeacherProfile）"""
    from apps.teachers.models import TeacherProfile
    from apps.users.models import User

    user = User.objects.create_user(
        username=username, password="pass12345", role=UserRole.TEACHER.value, status=1
    )
    TeacherProfile.objects.create(
        user=user, teacher_number=teacher_number, name=username, college=college
    )
    return user


def switch_state(year, state_value: int):
    """切换学年系统状态（阶段推进），用于验证「推进后不可撤销」"""
    state = SystemState.objects.get(academic_year=year)
    state.current_state = state_value
    state.save(update_fields=["current_state"])
    return state


def test_revoke_round1_approval_persists_and_restores_second_round_eligibility(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """正向：通过 -> 撤销 -> 录取被删除 + 申请变 REJECTED + 学生重新获得第二轮资格。"""
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )
    version_before = app.version

    resp = client_for(api_teacher_user).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code == 200, resp.content

    # 响应体是更新后的 ApplicationSerializer
    body = resp.json()["data"]
    assert body["id"] == app.id
    assert body["status"] == ApplicationStatus.REJECTED.value

    # 持久化：录取记录被删除（刷新后不会「恢复」）
    assert not Admission.objects.filter(application=app).exists()
    assert not Admission.objects.filter(
        academic_year=year, student_id=api_student_user.id
    ).exists()

    app.refresh_from_db()
    assert app.status == ApplicationStatus.REJECTED.value
    assert app.version == version_before + 1  # Repository 版本递增

    # 第二轮资格：第一轮已 REJECTED，进入第二轮开放阶段后可以重新申请
    switch_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    reapply = client_for(api_student_user).post(
        "/api/v2/applications/",
        {"academic_year": year.id, "teacher": api_teacher_user.id, "round": 2},
        format="json",
    )
    assert reapply.status_code in (200, 201), reapply.content
    new_admission = Admission.objects.get(
        academic_year=year, student_id=api_student_user.id
    )
    assert new_admission.source == AdmissionSource.ADMIT_ROUND2.value


def test_revoke_round1_approval_available_on_v1_compat_route(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """v1 兼容前缀复用同一 ViewSet，故撤销录取在 /api/v1/ 下同样可用。"""
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )

    resp = client_for(api_teacher_user).post(REVOKE_V1.format(id=app.id), {}, format="json")
    assert resp.status_code == 200, resp.content
    app.refresh_from_db()
    assert app.status == ApplicationStatus.REJECTED.value
    assert not Admission.objects.filter(application=app).exists()


def test_revoke_approval_by_another_teacher_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """他人导师不得撤销：403 + PERMISSION_DENIED，且不产生任何数据变更。"""
    other = make_other_teacher("t_revoke", "T9001")

    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    admission = make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )

    resp = client_for(other).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code == 403
    assert error_code(resp) == 12001  # PERMISSION_DENIED

    app.refresh_from_db()
    assert app.status == ApplicationStatus.APPROVED.value
    assert Admission.objects.filter(id=admission.id).exists()


def test_revoke_approval_after_phase_change_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """阶段推进（非 TEACHER_REVIEW）后不得撤销。"""
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    admission = make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )

    resp = client_for(api_teacher_user).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code >= 400
    assert error_code(resp) == 90002  # SYSTEM_STATE_INVALID_TRANSITION

    app.refresh_from_db()
    assert app.status == ApplicationStatus.APPROVED.value
    assert Admission.objects.filter(id=admission.id).exists()


def test_revoke_approval_does_not_touch_round2_or_unrelated_admissions(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """精确匹配：只删除本申请关联的 ADMIT_ROUND1，第二轮/人工分配记录必须保留。"""
    from apps.students.models import StudentProfile
    from apps.users.models import User

    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 5)

    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    target = make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )

    # 另一名学生的人工分配录取（与该申请无关）
    manual_student = User.objects.create_user(
        username="stu_manual", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=manual_student, student_number="S20240011", name="人工", major="计算机科学",
        class_name="A",
    )
    manual = make_admission(
        year, manual_student, api_teacher_user, source=AdmissionSource.MANUAL.value
    )

    # 第三名学生的第二轮录取（同样不得被删除）
    round2_student = User.objects.create_user(
        username="stu_round2", password="pass12345", role=UserRole.STUDENT.value, status=1
    )
    StudentProfile.objects.create(
        user=round2_student, student_number="S20240012", name="二轮", major="计算机科学",
        class_name="B",
    )
    round2_app = make_application(
        year, round2_student, api_teacher_user, ApplicationRound.SECOND_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    round2 = make_admission(
        year, round2_student, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND2.value, application=round2_app,
    )

    resp = client_for(api_teacher_user).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code == 200, resp.content

    assert not Admission.objects.filter(id=target.id).exists()
    assert Admission.objects.filter(id=manual.id).exists()
    assert Admission.objects.filter(id=round2.id).exists()
    assert Application.objects.filter(id=round2_app.id).exists()


def test_revoke_approval_on_round2_application_is_denied(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """第二轮申请不在本接口范围内：拒绝且第二轮录取记录保留。"""
    year = make_year()
    make_state(year, SystemStateValue.SECOND_ROUND_OPEN.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.SECOND_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    admission = make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND2.value, application=app,
    )

    resp = client_for(api_teacher_user).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code >= 400
    assert error_code(resp) == 50005  # APPLICATION_STATUS_INVALID
    assert Admission.objects.filter(id=admission.id).exists()


def test_revoke_approval_requires_matching_round1_admission(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """删除行数必须恰好为 1：来源不匹配时整体失败并回滚（申请仍 APPROVED）。"""
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    # 申请虽为 APPROVED，但关联录取来源是人工分配 -> 不是本接口应删除的对象
    manual = make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.MANUAL.value, application=app,
    )

    resp = client_for(api_teacher_user).post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert resp.status_code >= 400
    assert error_code(resp) == 60001  # ADMISSION_NOT_FOUND

    app.refresh_from_db()
    assert app.status == ApplicationStatus.APPROVED.value  # 事务回滚
    assert Admission.objects.filter(id=manual.id).exists()


def test_revoke_approval_twice_is_rejected(
    api_student_user, api_student_profile, api_teacher_user, api_teacher_profile
):
    """重复撤销被拒（状态已非 APPROVED），且不改变已撤销的结果。"""
    year = make_year()
    make_state(year, SystemStateValue.TEACHER_REVIEW.value)
    make_quota(year, api_teacher_user, 2)
    app = make_application(
        year, api_student_user, api_teacher_user, ApplicationRound.FIRST_ROUND.value,
        ApplicationStatus.APPROVED.value,
    )
    make_admission(
        year, api_student_user, api_teacher_user,
        source=AdmissionSource.ADMIT_ROUND1.value, application=app,
    )

    client = client_for(api_teacher_user)
    first = client.post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert first.status_code == 200, first.content

    second = client.post(REVOKE_V2.format(id=app.id), {}, format="json")
    assert second.status_code >= 400
    assert error_code(second) == 50006  # APPLICATION_ALREADY_PROCESSED

    app.refresh_from_db()
    assert app.status == ApplicationStatus.REJECTED.value
    assert not Admission.objects.filter(application=app).exists()
