"""Excel 数据导入器

逐行处理解析后的 Excel 数据，创建 user + profile，记录 import_log。

依据 DATABASE.md 7.9 Excel 导入流程：
3. 逐行处理（Importer 层）：
   BEGIN
     a. 校验行数据（必填字段、格式）
     b. 校验 username 不重复
     c. 创建 user + profile
     d. 创建 import_log (task_id, row_number, row_data, status=SUCCESS, created_user_id=?)
   COMMIT
   失败 → ROLLBACK，创建 import_log (status=FAILED, error_reason=?)

业务规则（PROJECT.md 7.13）：
- 单行失败不阻塞整批
- 重复 username 跳过该行，标记为失败
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from apps.common.enums import ImportRowStatus, UserRole, UserStatus
from apps.common.logger import get_logger
from apps.imports.excel.validator import RowValidator
from apps.imports.models import ImportLog, ImportTask
from apps.imports.repositories import ImportLogRepository
from apps.monitoring.services import MetricsService
from apps.students.models import StudentProfile
from apps.students.repositories import StudentProfileRepository
from apps.teachers.models import TeacherProfile
from apps.teachers.repositories import TeacherProfileRepository
from apps.users.models import AdminProfile, User
from apps.users.repositories import (
    AdminProfileRepository,
    UserRepository,
)

logger = get_logger("imports.excel.importer")


@dataclass
class ImportResult:
    """单行导入结果"""

    row_number: int
    success: bool
    error_reason: str | None = None
    created_user_id: int | None = None


@dataclass
class BatchImportResult:
    """批次导入结果"""

    total_rows: int = 0
    success_count: int = 0
    failed_count: int = 0
    results: list[ImportResult] = field(default_factory=list)
    # 累积的校验阶段耗时（秒），供外部记录 validate 阶段 metric
    validate_duration: float = 0.0

    def add(self, result: ImportResult) -> None:
        self.results.append(result)
        if result.success:
            self.success_count += 1
        else:
            self.failed_count += 1


class ExcelImporter:
    """Excel 数据导入器

    逐行处理 Excel 数据，每行独立事务，单行失败不阻塞整批。
    """

    def __init__(self):
        self.user_repository = UserRepository()
        self.student_repository = StudentProfileRepository()
        self.teacher_repository = TeacherProfileRepository()
        self.admin_repository = AdminProfileRepository()
        self.log_repository = ImportLogRepository()

    def import_rows(
        self,
        task: ImportTask,
        rows: list[dict[str, Any]],
        role: int,
    ) -> BatchImportResult:
        """导入多行数据

        Args:
            task: 导入任务实例
            rows: 解析后的行数据列表
            role: UserRole 枚举值

        Returns:
            批次导入结果（含累积的 validate_duration）
        """
        batch_result = BatchImportResult(total_rows=len(rows))

        for row_data in rows:
            row_number = row_data.pop("_row_number", 0)
            result, validate_time = self._import_single_row(
                task, row_data, row_number, role
            )
            batch_result.add(result)
            batch_result.validate_duration += validate_time

        return batch_result

    def _import_single_row(
        self,
        task: ImportTask,
        row_data: dict[str, Any],
        row_number: int,
        role: int,
    ) -> tuple[ImportResult, float]:
        """导入单行数据（独立事务）

        失败时自动 ROLLBACK，并记录 import_log (status=FAILED)。

        Returns:
            (导入结果, 校验阶段耗时秒数)
        """
        row_data_str = json.dumps(row_data, ensure_ascii=False, default=str)
        validate_time = 0.0

        try:
            with transaction.atomic():
                # a. 校验行数据（计时）
                validate_start = time.perf_counter()
                errors = RowValidator.validate(row_data, role)
                validate_time = time.perf_counter() - validate_start
                if errors:
                    raise ValueError("; ".join(errors))

                # b. 校验 username 不重复
                username = row_data.get("username")
                if not username:
                    raise ValueError("用户名不能为空")

                if self.user_repository.exists(username=username):
                    raise ValueError(f"用户名 {username} 已存在")

                # c. 创建 user + profile
                created_user = self._create_user_with_profile(row_data, role)

                # d. 创建 import_log (status=SUCCESS)
                self.log_repository.create(
                    task=task,
                    row_number=row_number,
                    row_data=row_data_str,
                    status=ImportRowStatus.SUCCESS.value,
                    created_user=created_user,
                )

                logger.info(
                    "Import row success: task=%s, row=%s, user=%s",
                    task.id, row_number, created_user.id,
                )
                return ImportResult(
                    row_number=row_number,
                    success=True,
                    created_user_id=created_user.id,
                ), validate_time

        except Exception as exc:
            # 失败 → 记录 import_log (status=FAILED)
            error_reason = str(exc)[:255]
            self._create_failure_log(task, row_number, row_data_str, error_reason)
            logger.warning(
                "Import row failed: task=%s, row=%s, reason=%s",
                task.id, row_number, error_reason,
            )
            return ImportResult(
                row_number=row_number,
                success=False,
                error_reason=error_reason,
            ), validate_time

    def _create_user_with_profile(
        self, row_data: dict[str, Any], role: int
    ) -> User:
        """创建 user + 对应 profile"""
        username = row_data.get("username")
        # PROJECT.md R11-09 / PC-10：未填则系统生成默认密码 Mentor@{username}
        password = row_data.get("password") or f"Mentor@{username}"

        # 创建 User（DATABASE.md 4.2：导入用户初始状态为未激活）
        user = User(
            username=username,
            role=role,
            status=UserStatus.USER_INACTIVE.value,
        )
        user.set_password(password)
        user.save()

        # 创建对应 Profile
        if role == UserRole.STUDENT.value:
            self._create_student_profile(user, row_data)
        elif role == UserRole.TEACHER.value:
            self._create_teacher_profile(user, row_data)
        elif role == UserRole.ADMIN.value:
            self._create_admin_profile(user, row_data)

        return user

    def _create_student_profile(self, user: User, row_data: dict[str, Any]) -> None:
        """创建学生档案"""
        StudentProfile.objects.create(
            user=user,
            student_number=row_data.get("student_number"),
            name=row_data.get("name"),
            major=row_data.get("major"),
            class_name=row_data.get("class_name"),
        )

    def _create_teacher_profile(self, user: User, row_data: dict[str, Any]) -> None:
        """创建导师档案"""
        TeacherProfile.objects.create(
            user=user,
            teacher_number=row_data.get("teacher_number"),
            name=row_data.get("name"),
            college=row_data.get("college"),
            title=row_data.get("title") or "",
            research_area=row_data.get("research_area") or "",
        )

    def _create_admin_profile(self, user: User, row_data: dict[str, Any]) -> None:
        """创建管理员档案"""
        AdminProfile.objects.create(
            user=user,
            name=row_data.get("name"),
        )

    def _create_failure_log(
        self,
        task: ImportTask,
        row_number: int,
        row_data_str: str,
        error_reason: str,
    ) -> None:
        """创建失败日志（独立事务，确保即使主事务回滚也能记录）"""
        try:
            with transaction.atomic():
                ImportLog.objects.create(
                    task=task,
                    row_number=row_number,
                    row_data=row_data_str,
                    status=ImportRowStatus.FAILED.value,
                    error_reason=error_reason,
                )
        except Exception as log_exc:
            logger.error(
                "Failed to create failure log: task=%s, row=%s, error=%s",
                task.id, row_number, log_exc,
            )
