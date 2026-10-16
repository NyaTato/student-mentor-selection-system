"""
导入管理 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.enums import ImportRowStatus, ImportTaskStatus, UserRole
from apps.common.models import TimeStampedModel


class ImportTask(TimeStampedModel):
    """Excel 导入任务 - 异步处理，记录任务状态和统计"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="import_tasks",
        verbose_name="所属学年",
    )
    role = models.PositiveSmallIntegerField("导入角色", choices=UserRole.choices)
    status = models.PositiveSmallIntegerField(
        "任务状态",
        choices=ImportTaskStatus.choices,
        default=ImportTaskStatus.PENDING.value,
    )
    file_name = models.CharField("原始文件名", max_length=255)
    file_size = models.PositiveBigIntegerField("文件大小")
    total_rows = models.PositiveIntegerField("总行数", default=0)
    success_count = models.PositiveIntegerField("成功行数", default=0)
    failed_count = models.PositiveIntegerField("失败行数", default=0)
    error_message = models.CharField(
        "任务级错误", max_length=512, null=True, blank=True
    )
    started_at = models.DateTimeField("开始处理时间", null=True, blank=True)
    finished_at = models.DateTimeField("完成时间", null=True, blank=True)
    triggered_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        db_column="triggered_by",
        related_name="import_tasks",
        verbose_name="触发管理员",
    )
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        db_table = "import_task"
        verbose_name = "导入任务"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "created_at"],
                name="idx_importtask_year_created",
            ),
            models.Index(fields=["status"], name="idx_importtask_status"),
        ]

    def __str__(self):
        return f"import {self.id} {self.file_name}"


class ImportLog(models.Model):
    """导入日志 - 每行一条记录，只追加，不可修改、不可删除"""

    task = models.ForeignKey(
        "imports.ImportTask",
        on_delete=models.PROTECT,
        db_column="task_id",
        related_name="logs",
        verbose_name="所属任务",
    )
    row_number = models.PositiveIntegerField("行号")
    row_data = models.TextField("行数据")
    status = models.PositiveSmallIntegerField("状态", choices=ImportRowStatus.choices)
    error_reason = models.CharField(
        "失败原因", max_length=255, null=True, blank=True
    )
    created_user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        db_column="created_user_id",
        related_name="created_import_logs",
        null=True,
        blank=True,
        verbose_name="创建的用户",
    )
    created_at = models.DateTimeField("记录时间", auto_now_add=True)

    class Meta:
        db_table = "import_log"
        verbose_name = "导入日志"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["task", "status"],
                name="idx_task_status",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["task", "row_number"],
                name="uk_task_row",
            ),
        ]

    def __str__(self):
        return f"task {self.task_id} row {self.row_number}"
