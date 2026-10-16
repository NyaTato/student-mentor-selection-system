"""
公告管理 Repository
"""
from apps.announcements.models import Announcement
from apps.common.repositories import BaseRepository


class AnnouncementRepository(BaseRepository):
    """公告 Repository"""

    model = Announcement

    def get_queryset(self):
        return self.model.objects.select_related(
            "academic_year", "created_by"
        ).all()

    def list_by_academic_year(
        self, academic_year_id: int, only_published: bool = False
    ):
        """按学年查询公告"""
        qs = self.get_queryset().filter(academic_year_id=academic_year_id)
        if only_published:
            qs = qs.filter(is_published=True)
        return qs
