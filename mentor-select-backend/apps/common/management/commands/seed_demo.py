"""隔离演示数据库种子命令（仅限 demo settings 使用）。

安全设计（按 Task 04 要求）：
- 本命令在任何写操作之前执行双重守卫：``settings.DEMO_MODE`` 必须为 True，
  且默认数据库必须是 SQLite 文件 ``<backend>/work/demo.sqlite3``；
  任何其他数据库一律拒绝，绝不写入、不清库。
- 登录密码绝不硬编码：可用 ``--password`` 或 ``SMSP_DEMO_PASSWORD`` 环境变量
  指定；均未提供时按进程随机生成（仅打印一次给操作员，不写入任何文件）。
- 全部使用 ``get_or_create`` / ``update_or_create`` 且不删除任何已有数据，
  重复执行不会产生重复记录；不播种任何录取（admission）数据，
  以便在浏览器中完整演练申请 / 审核 / 撤销 / 人工分配流程。
- 所有人物、学校、联系方式均为虚构（演示学院/演示专业，无真实电话），
  账号仅供本地查看。
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from apps.academic_year.models import AcademicYear
from apps.announcements.models import Announcement
from apps.common.enums import (
    AcademicYearStatus,
    StateTransitionType,
    SystemStateValue,
    UserRole,
    UserStatus,
)
from apps.students.models import StudentProfile
from apps.system.models import StateHistory, SystemState
from apps.teachers.models import TeacherProfile, TeacherQuota
from apps.users.models import AdminProfile, User

# 虚构演示账号（用户名固定，密码永不硬编码）
DEMO_ADMIN_USERNAME = "demo_admin"
DEMO_TEACHER_USERNAMES = ("demo_teacher", "demo_teacher2")
DEMO_STUDENT_SPECS = (
    # (username, student_number, name)
    ("demo_student", "DEMO0001", "演示学生甲"),
    ("demo_student2", "DEMO0002", "演示学生乙"),
    ("demo_student3", "DEMO0003", "演示学生丙"),
)

DEMO_YEAR_NAME = "2026-2027"
DEMO_YEAR_START = 2026
DEMO_YEAR_END = 2027
DEMO_TEACHER_QUOTA = 2

DEMO_ANNOUNCEMENT_TITLE = "演示公告：2026-2027 学年导师选择流程说明（虚构示例）"
DEMO_ANNOUNCEMENT_CONTENT = (
    "【本地演示虚构公告】\n"
    "欢迎使用本地隔离演示环境。当前学年为 2026-2027，第一轮申请已开放。\n"
    "演示账号：demo_admin（管理员）、demo_teacher / demo_teacher2（导师）、"
    "demo_student / demo_student2 / demo_student3（学生）。\n"
    "请在浏览器中演练申请、审核、撤销与人工分配流程；"
    "需要真实 Redis 的自动状态切换/自动分配在最小演示中不可用。"
)


def _expected_demo_db_path() -> Path:
    """返回演示数据库的唯一合法路径（<backend>/work/demo.sqlite3）。"""
    base_dir = Path(getattr(settings, "BASE_DIR", "."))
    return base_dir / "work" / "demo.sqlite3"


def _guard_demo_database() -> None:
    """写操作前的双重守卫：DEMO_MODE 与 SQLite 文件路径必须同时满足。"""
    if not getattr(settings, "DEMO_MODE", False):
        raise CommandError(
            "拒绝执行：当前 settings 未启用 DEMO_MODE。"
            "请使用 --settings=config.settings.demo 运行本命令。"
        )
    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    name = settings.DATABASES.get("default", {}).get("NAME", "")
    expected = _expected_demo_db_path()
    try:
        same_file = Path(str(name)).resolve() == expected.resolve()
    except OSError:
        same_file = False
    if engine != "django.db.backends.sqlite3" or not same_file:
        raise CommandError(
            "拒绝执行：默认数据库不是预期的隔离演示库。\n"
            f"期望 ENGINE=django.db.backends.sqlite3 且 NAME={expected}，"
            f"实际 ENGINE={engine} NAME={name}。"
            "为保护真实数据，本命令不会写入任何其他数据库。"
        )
    # 额外一致性校验：实际连接配置同样必须指向该文件（防止路由/覆盖异常）。
    vendor = connection.vendor
    db_name = connection.settings_dict.get("NAME", "")
    if vendor != "sqlite" or str(Path(str(db_name)).resolve()) != str(expected.resolve()):
        raise CommandError(
            "拒绝执行：实际数据库连接与预期演示库不一致，"
            "为保护数据已中止（未写入任何内容）。"
        )


def _resolve_password(option_password: str | None) -> tuple[str, bool]:
    """解析演示登录密码：命令行 > 环境变量 > 随机生成（绝不硬编码）。"""
    if option_password and option_password.strip():
        password = option_password.strip()
        generated = False
    else:
        env_password = os.environ.get("SMSP_DEMO_PASSWORD", "")
        if env_password.strip():
            password = env_password.strip()
            generated = False
        else:
            password = secrets.token_urlsafe(16)
            generated = True
    if len(password) < 8:
        raise CommandError("演示密码长度至少 8 位（Django 最小长度要求）。")
    return password, generated


def _upsert_user(username: str, *, role: int, password: str) -> User:
    """幂等创建/更新演示用户：canonical set_password，角色/状态/激活标志齐全。"""
    user, _ = User.all_objects.update_or_create(
        username=username,
        defaults={
            "role": role,
            "status": UserStatus.ACTIVE,
            "is_active": True,
            "deleted_at": None,
        },
    )
    user.role = role
    user.status = UserStatus.ACTIVE
    user.is_active = True
    user.deleted_at = None
    # 管理员账号需要进 Django admin，普通演示账号不需要 staff/superuser。
    user.is_staff = role == UserRole.ADMIN
    user.is_superuser = False
    user.set_password(password)
    user.save()
    return user


class Command(BaseCommand):
    help = "向隔离演示库（work/demo.sqlite3）幂等播种演示账号与基础配置。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            dest="password",
            default=None,
            help="所有演示账号的登录密码（也可使用 SMSP_DEMO_PASSWORD 环境变量；"
            "均未提供则随机生成并仅打印一次）。",
        )

    def handle(self, *args, **options):
        # 守卫必须在任何写操作之前执行。
        _guard_demo_database()
        password, generated = _resolve_password(options.get("password"))
        now = timezone.now()

        # ---- 用户与档案（幂等，不删除任何已有数据）----
        admin_user = _upsert_user(
            DEMO_ADMIN_USERNAME, role=UserRole.ADMIN, password=password
        )
        AdminProfile.all_objects.update_or_create(
            user=admin_user,
            defaults={"name": "演示管理员", "deleted_at": None},
        )

        teacher_profiles: list[TeacherProfile] = []
        for index, username in enumerate(DEMO_TEACHER_USERNAMES, start=1):
            teacher_user = _upsert_user(
                username, role=UserRole.TEACHER, password=password
            )
            profile, _ = TeacherProfile.all_objects.update_or_create(
                user=teacher_user,
                defaults={
                    "teacher_number": f"DEMOT{index:03d}",
                    "name": f"演示导师{'甲' if index == 1 else '乙'}",
                    "college": "演示学院",
                    "title": "副教授",
                    "research_area": "演示研究方向（虚构）",
                    "profile": "本地演示用虚构导师简介。",
                    "deleted_at": None,
                },
            )
            teacher_profiles.append(profile)

        for username, number, name in DEMO_STUDENT_SPECS:
            student_user = _upsert_user(
                username, role=UserRole.STUDENT, password=password
            )
            StudentProfile.all_objects.update_or_create(
                user=student_user,
                defaults={
                    "student_number": number,
                    "name": name,
                    "major": "演示专业",
                    "class_name": "演示班01",
                    "department": "演示学院",
                    "phone": None,
                    "deleted_at": None,
                },
            )

        # ---- 学年（canonical 2026-2027，ACTIVE 全局唯一需先收敛其他行）----
        AcademicYear.all_objects.filter(
            status=AcademicYearStatus.ACTIVE
        ).exclude(name=DEMO_YEAR_NAME).update(status=AcademicYearStatus.INACTIVE)
        year, _ = AcademicYear.all_objects.update_or_create(
            name=DEMO_YEAR_NAME,
            defaults={
                "start_year": DEMO_YEAR_START,
                "end_year": DEMO_YEAR_END,
                "status": AcademicYearStatus.ACTIVE,
                "deleted_at": None,
            },
        )
        if year.activated_at is None:
            year.activated_at = now
            year.save(update_fields=["activated_at", "updated_at"])

        # ---- 系统状态（FIRST_ROUND_OPEN；重复执行保持幂等）----
        state, created = SystemState.objects.get_or_create(
            academic_year=year,
            defaults={
                "current_state": SystemStateValue.FIRST_ROUND_OPEN,
                "previous_state": SystemStateValue.INIT,
                "state_changed_at": now,
            },
        )
        if not created and state.current_state != SystemStateValue.FIRST_ROUND_OPEN:
            state.previous_state = state.current_state
            state.current_state = SystemStateValue.FIRST_ROUND_OPEN
            state.state_changed_at = now
            state.save()
        if not StateHistory.objects.filter(academic_year=year).exists():
            StateHistory.objects.create(
                academic_year=year,
                from_state=SystemStateValue.INIT,
                to_state=SystemStateValue.FIRST_ROUND_OPEN,
                transition_type=StateTransitionType.FORWARD,
                reason="本地演示初始化（seed_demo）",
                operator=admin_user,
            )

        # ---- 导师名额（每位演示导师 2 个，学年+导师唯一约束下幂等）----
        for profile in teacher_profiles:
            TeacherQuota.all_objects.update_or_create(
                academic_year=year,
                teacher=profile,
                defaults={"max_quota": DEMO_TEACHER_QUOTA, "deleted_at": None},
            )

        # ---- 已发布虚构公告（按学年+标题幂等，不产生重复）----
        # 注意：created_by 为必填外键，必须进 defaults，否则首次创建会违反非空约束。
        announcement, _ = Announcement.all_objects.update_or_create(
            academic_year=year,
            title=DEMO_ANNOUNCEMENT_TITLE,
            defaults={
                "content": DEMO_ANNOUNCEMENT_CONTENT,
                "is_published": True,
                "created_by": admin_user,
                "deleted_at": None,
            },
        )
        if announcement.published_at is None:
            announcement.published_at = now
            announcement.save(update_fields=["published_at", "updated_at"])

        # 注意：故意不播种任何申请/录取数据，浏览器可完整演练业务流程。
        # 需要真实 Redis 的自动状态切换/自动分配在最小演示中不可用。

        self.stdout.write(
            "演示种子写入完成（隔离库 work/demo.sqlite3，未清理任何已有数据）。"
        )
        self.stdout.write(
            "账号：demo_admin / demo_teacher / demo_teacher2 / "
            "demo_student / demo_student2 / demo_student3"
        )
        if generated:
            self.stdout.write(
                f"本次随机生成的演示密码（仅显示一次，请妥善转告本地操作员）：{password}"
            )
        else:
            self.stdout.write("已使用操作员提供的密码（--password 或 SMSP_DEMO_PASSWORD）。")
        self.stdout.write(
            "提示：以上账号与密码仅供本地演示查看；JWT 由演示密钥签发，与生产密钥无关。"
        )
