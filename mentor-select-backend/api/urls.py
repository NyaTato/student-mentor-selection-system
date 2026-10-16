"""api/urls.py - API v2 路由

为避免与现有 apps/* 路由（/api/v1/）冲突，新模块路由统一使用 /api/v2/ 前缀。

业务路由说明（v2 业务闭环）
--------------------------
v2 业务路由（applications / assignments / announcements / system /
statistics / academic-years / teachers）**直接复用** apps/* 的
View / Serializer / Service / Repository 实现，不新建业务模型、不复制业务逻辑。
v1（/api/v1/...）保留同一批 View，作为兼容适配层（thin compatibility adapter），
两条路径共享同一份实现与同一份数据 —— 因此 v1 与 v2 读取到的业务状态天然一致。
"""
from django.urls import include, path

from api.views.admin import (
    create_admin,
    delete_admin,
    get_admin,
    get_admin_by_user_id,
    list_admins,
    update_admin,
)
from api.views.smoke import smoke
from api.views.student import (
    create_student,
    delete_student,
    get_student,
    get_student_by_student_number,
    get_student_by_user_id,
    list_students,
    update_student,
    update_student_phone,
)
from api.views.teacher import (
    create_teacher,
    delete_teacher,
    get_teacher,
    get_teacher_by_teacher_number,
    get_teacher_by_user_id,
    list_teachers,
    update_teacher,
)
from api.views.user import (
    change_password,
    create_user,
    delete_user,
    disable_user,
    enable_user,
    get_user,
    list_users,
    login,
    reset_password,
    update_user,
)

urlpatterns = [
    # 健康检查
    path("smoke", smoke, name="api_smoke"),

    # ===== User 用户管理 =====
    path("users/login", login, name="api_user_login"),
    path("users/list", list_users, name="api_user_list"),
    path("users/create", create_user, name="api_user_create"),
    path("users/<int:user_id>", get_user, name="api_user_detail"),
    path("users/<int:user_id>/update", update_user, name="api_user_update"),
    path("users/<int:user_id>/change_password", change_password, name="api_user_change_password"),
    path("users/<int:user_id>/reset_password", reset_password, name="api_user_reset_password"),
    path("users/<int:user_id>/disable", disable_user, name="api_user_disable"),
    path("users/<int:user_id>/enable", enable_user, name="api_user_enable"),
    path("users/<int:user_id>/delete", delete_user, name="api_user_delete"),

    # ===== Student 学生管理 =====
    path("students/list", list_students, name="api_student_list"),
    path("students/create", create_student, name="api_student_create"),
    path("students/<int:student_id>", get_student, name="api_student_detail"),
    path("students/by_user/<int:user_id>", get_student_by_user_id, name="api_student_by_user"),
    path("students/by_number/<str:student_number>", get_student_by_student_number, name="api_student_by_number"),
    path("students/<int:student_id>/update", update_student, name="api_student_update"),
    path("students/<int:student_id>/phone", update_student_phone, name="api_student_phone"),
    path("students/<int:student_id>/delete", delete_student, name="api_student_delete"),

    # ===== Teacher 导师管理 =====
    path("teachers/list", list_teachers, name="api_teacher_list"),
    path("teachers/create", create_teacher, name="api_teacher_create"),
    path("teachers/<int:teacher_id>", get_teacher, name="api_teacher_detail"),
    path("teachers/by_user/<int:user_id>", get_teacher_by_user_id, name="api_teacher_by_user"),
    path("teachers/by_number/<str:teacher_number>", get_teacher_by_teacher_number, name="api_teacher_by_number"),
    path("teachers/<int:teacher_id>/update", update_teacher, name="api_teacher_update"),
    path("teachers/<int:teacher_id>/delete", delete_teacher, name="api_teacher_delete"),

    # ===== Admin 管理员管理 =====
    path("admins/list", list_admins, name="api_admin_list"),
    path("admins/create", create_admin, name="api_admin_create"),
    path("admins/<int:admin_id>", get_admin, name="api_admin_detail"),
    path("admins/by_user/<int:user_id>", get_admin_by_user_id, name="api_admin_by_user"),
    path("admins/<int:admin_id>/update", update_admin, name="api_admin_update"),
    path("admins/<int:admin_id>/delete", delete_admin, name="api_admin_delete"),

    # ===== v2 业务路由（复用 canonical apps 实现，与 v1 共享同一批 View）=====
    # 申请：/api/v2/applications/、/my/、/teacher/、{id}/approve/、{id}/reject/、
    #       /batch-approve/、/batch-reject/、{id}/cancel/
    path("applications/", include("apps.applications.urls")),
    # 分配：/api/v2/assignments/admissions/、/auto-logs/、/manual-assign/、
    #       /auto-assign/preview|run|revoke/
    path("assignments/", include("apps.assignments.urls")),
    # 公告：/api/v2/announcements/
    path("announcements/", include("apps.announcements.urls")),
    # 系统状态与历史：/api/v2/system/states/、/schedules/、/histories/
    path("system/", include("apps.system.urls")),
    # 统计：/api/v2/statistics/dashboard/、/applications/、/admissions/、/teachers/
    path("statistics/", include("apps.statistics.urls")),
    # 学年：/api/v2/academic-years/
    path("academic-years/", include("apps.academic_year.urls")),
    # 导师档案与名额：/api/v2/teachers/profiles/、/profiles/directory/、/quotas/
    path("teachers/", include("apps.teachers.urls")),
]
