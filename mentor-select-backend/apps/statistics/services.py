"""统计服务

提供 Dashboard、申请、录取、导师名额使用情况统计。

依据 PROJECT.md / DATABASE.md：
- Dashboard：学生总数、导师总数、申请总数、录取总数、未录取学生数、各状态申请数
- 申请统计：按状态分组的申请数量
- 录取统计：按来源分组的录取数量
- 导师名额统计：每位导师的 max_quota / admitted_count / remaining_quota
"""
from __future__ import annotations

from apps.applications.repositories import ApplicationRepository
from apps.assignments.repositories import AdmissionRepository
from apps.common.enums import (
    AdmissionSource,
    ApplicationRound,
    ApplicationStatus,
)
from apps.common.logger import get_logger
from apps.students.repositories import StudentProfileRepository
from apps.system.repositories import SystemStateRepository
from apps.teachers.repositories import TeacherProfileRepository, TeacherQuotaRepository

logger = get_logger("statistics.services")


def _label_from_choices(choices: list[tuple[int, str]], value: int) -> str:
    """将枚举值转换为可读标签（消除重复的 dict(...).get(...) 调用）

    Args:
        choices: Django choices 列表 [(value, label), ...]
        value: 枚举值

    Returns:
        对应的 label，未匹配返回 str(value)
    """
    for v, label in choices:
        if v == value:
            return label
    return str(value)


def _group_by_label(choices: list[tuple[int, str]], rows: list[dict], key: str) -> dict[str, int]:
    """将分组计数结果转换为 {label: count}（消除重复逻辑）

    Args:
        choices: Django choices 列表
        rows: Repository 返回的分组结果 [{key: int, "count": int}, ...]
        key: 分组字段名

    Returns:
        {label: count}
    """
    return {
        _label_from_choices(choices, row[key]): row["count"]
        for row in rows
    }


class StatisticsService:
    """统计服务

    纯聚合查询服务，不绑定单个 Repository，故不继承 BaseService。
    Service 层负责跨模块编排（students + assignments + applications + teachers + system），
    Repository 层保持模块独立性。
    """

    def __init__(self):
        self.student_repo = StudentProfileRepository()
        self.teacher_repo = TeacherProfileRepository()
        self.application_repo = ApplicationRepository()
        self.admission_repo = AdmissionRepository()
        self.quota_repo = TeacherQuotaRepository()
        self.state_repo = SystemStateRepository()

    def get_dashboard(self, academic_year_id: int) -> dict:
        """获取 Dashboard 统计数据

        Args:
            academic_year_id: 学年 ID

        Returns:
            {
                "academic_year_id": int,
                "total_students": int,
                "total_teachers": int,
                "total_applications": int,
                "total_admissions": int,
                "unassigned_students": int,
                "applications_by_status": {status: count, ...},
                "admissions_by_source": {source: count, ...},
                "current_state": int | None,
                "current_state_display": str | None,
            }
        """
        total_students = self.student_repo.count()
        total_teachers = self.teacher_repo.count()
        total_applications = self.application_repo.count(academic_year_id=academic_year_id)
        total_admissions = self.admission_repo.count(academic_year_id=academic_year_id)

        # 未分配学生数：Service 层从 AdmissionRepository 获取已录取列表，传入 StudentRepository
        assigned_ids = self.admission_repo.list_assigned_student_ids(academic_year_id)
        unassigned_students = self.student_repo.count_unassigned(
            excluded_user_ids=assigned_ids
        )

        # 按状态分组的申请数（通过 helper 消除重复）
        applications_by_status = _group_by_label(
            ApplicationStatus.choices,
            self.application_repo.count_group_by_status(academic_year_id),
            "status",
        )

        # 按来源分组的录取数
        admissions_by_source = _group_by_label(
            AdmissionSource.choices,
            self.admission_repo.count_group_by_source(academic_year_id),
            "source",
        )

        # 当前系统状态
        current_state = None
        current_state_display = None
        state = self.state_repo.get_by_academic_year(academic_year_id)
        if state is not None:
            current_state = state.current_state
            current_state_display = state.get_current_state_display()
        else:
            logger.warning("SystemState not found for year=%s", academic_year_id)

        return {
            "academic_year_id": academic_year_id,
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_applications": total_applications,
            "total_admissions": total_admissions,
            "unassigned_students": unassigned_students,
            "applications_by_status": applications_by_status,
            "admissions_by_source": admissions_by_source,
            "current_state": current_state,
            "current_state_display": current_state_display,
        }

    def get_applications_statistics(self, academic_year_id: int) -> dict:
        """获取申请统计

        Returns:
            {
                "total": int,
                "by_status": {status_name: count, ...},
                "by_round": {round_name: count, ...},
                "by_teacher": [{teacher_id, teacher_number, teacher_name, count}, ...],
            }
        """
        total = self.application_repo.count(academic_year_id=academic_year_id)

        by_status = _group_by_label(
            ApplicationStatus.choices,
            self.application_repo.count_group_by_status(academic_year_id),
            "status",
        )

        by_round = _group_by_label(
            ApplicationRound.choices,
            self.application_repo.count_group_by_round(academic_year_id),
            "round",
        )

        # 按导师分组（Repository 已归一化字段名，Service 层直接使用）
        by_teacher = list(self.application_repo.count_group_by_teacher(academic_year_id))

        return {"total": total, "by_status": by_status, "by_round": by_round, "by_teacher": by_teacher}

    def get_admissions_statistics(self, academic_year_id: int) -> dict:
        """获取录取统计

        Returns:
            {
                "total": int,
                "by_source": {source_name: count, ...},
                "by_teacher": [{teacher_id, teacher_name, count, max_quota, remaining}, ...],
            }
        """
        total = self.admission_repo.count(academic_year_id=academic_year_id)

        by_source = _group_by_label(
            AdmissionSource.choices,
            self.admission_repo.count_group_by_source(academic_year_id),
            "source",
        )

        # 按导师分组 + 名额使用情况
        by_teacher = []
        teachers = self.quota_repo.list_with_remaining(academic_year_id)
        for t in teachers:
            by_teacher.append({
                "teacher_id": t["teacher_id"],
                "teacher_number": t["teacher_number"],
                "teacher_name": t["name"],
                "count": t["admitted_count"],
                "max_quota": t["max_quota"],
                "remaining": t["remaining_quota"],
            })

        # 按录取数降序排序
        by_teacher.sort(key=lambda x: -x["count"])
        return {"total": total, "by_source": by_source, "by_teacher": by_teacher}

    def get_teachers_quota_statistics(self, academic_year_id: int) -> dict:
        """获取导师名额使用情况统计

        Returns:
            {
                "total_teachers": int,
                "total_quota": int,
                "total_admitted": int,
                "total_remaining": int,
                "teachers": [{teacher_id, teacher_number, teacher_name, max_quota, admitted, remaining, utilization}, ...],
            }
        """
        teachers_data = self.quota_repo.list_with_remaining(academic_year_id)

        teachers = []
        total_quota = 0
        total_admitted = 0

        for t in teachers_data:
            utilization = round(t["admitted_count"] / t["max_quota"] * 100, 2) if t["max_quota"] > 0 else 0.0
            teachers.append({
                "teacher_id": t["teacher_id"],
                "teacher_number": t["teacher_number"],
                "teacher_name": t["name"],
                "max_quota": t["max_quota"],
                "admitted": t["admitted_count"],
                "remaining": t["remaining_quota"],
                "utilization": utilization,
            })
            total_quota += t["max_quota"]
            total_admitted += t["admitted_count"]

        # 按利用率降序排序
        teachers.sort(key=lambda x: -x["utilization"])

        return {
            "total_teachers": len(teachers),
            "total_quota": total_quota,
            "total_admitted": total_admitted,
            "total_remaining": total_quota - total_admitted,
            "teachers": teachers,
        }
