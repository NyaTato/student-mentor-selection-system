"""
系统状态 Models
依据 DATABASE.md 第三部分字段设计
"""
from django.db import models

from apps.common.enums import StateTransitionType, SystemStateValue
from apps.common.models import TimeStampedModel


class SystemState(TimeStampedModel):
    """系统状态 - 按学年分行，每个 academic_year 一条记录"""

    academic_year = models.OneToOneField(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="system_state",
        verbose_name="所属学年",
    )
    current_state = models.PositiveSmallIntegerField(
        "当前状态",
        choices=SystemStateValue.choices,
        default=SystemStateValue.INIT,
    )
    previous_state = models.PositiveSmallIntegerField(
        "上一状态", choices=SystemStateValue.choices, null=True, blank=True
    )
    state_changed_at = models.DateTimeField("当前状态开始时间")
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        db_table = "system_state"
        verbose_name = "系统状态"
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    def __str__(self):
        return f"{self.academic_year_id} -> {self.get_current_state_display()}"


class SystemStateSchedule(TimeStampedModel):
    """自动状态切换配置 - 每个学年一条记录，与 system_state 一对一"""

    academic_year = models.OneToOneField(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="state_schedule",
        verbose_name="所属学年",
    )
    first_round_start_at = models.DateTimeField(
        "第一轮开始时间", null=True, blank=True
    )
    first_round_end_at = models.DateTimeField(
        "第一轮结束时间", null=True, blank=True
    )
    teacher_review_end_at = models.DateTimeField(
        "导师审核结束时间", null=True, blank=True
    )
    second_round_end_at = models.DateTimeField(
        "第二轮结束时间", null=True, blank=True
    )
    auto_enabled = models.BooleanField("自动切换开关", default=False)
    version = models.PositiveIntegerField("乐观锁版本", default=1)

    class Meta:
        db_table = "system_state_schedule"
        verbose_name = "自动状态切换配置"
        verbose_name_plural = verbose_name
        ordering = ["-id"]

    def __str__(self):
        return f"schedule {self.academic_year_id}"


class StateHistory(models.Model):
    """状态变更历史 - 只追加，不可修改、不可删除"""

    academic_year = models.ForeignKey(
        "academic_year.AcademicYear",
        on_delete=models.PROTECT,
        db_column="academic_year_id",
        related_name="state_histories",
        verbose_name="所属学年",
    )
    from_state = models.PositiveSmallIntegerField(
        "转换前状态", choices=SystemStateValue.choices
    )
    to_state = models.PositiveSmallIntegerField(
        "转换后状态", choices=SystemStateValue.choices
    )
    transition_type = models.PositiveSmallIntegerField(
        "转换类型", choices=StateTransitionType.choices
    )
    reason = models.CharField("回退原因", max_length=512, null=True, blank=True)
    operator = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        db_column="operator_id",
        related_name="state_histories",
        null=True,
        blank=True,
        verbose_name="操作人",
    )
    created_at = models.DateTimeField("转换时间", auto_now_add=True)

    class Meta:
        db_table = "state_history"
        verbose_name = "状态变更历史"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        indexes = [
            models.Index(
                fields=["academic_year", "created_at"],
                name="idx_statehist_year_created",
            ),
        ]

    def __str__(self):
        return f"{self.from_state} -> {self.to_state}"
