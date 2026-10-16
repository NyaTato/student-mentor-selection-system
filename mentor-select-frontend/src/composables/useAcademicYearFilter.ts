/**
 * 学年数据过滤 composable — R9-09/R9-10
 *
 * 业务数据（申请、录取、公告）通过 academic_year_id 隔离。
 * 学生和导师仅可见当前 ACTIVE 学年的数据。
 * 管理员可切换查看历史学年数据（只读）。
 */
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useSharedStore } from '@/stores/shared'

export function useAcademicYearFilter() {
  const sharedStore = useSharedStore()
  const { applications, admissions, announcements, currentAcademicYearId } =
    storeToRefs(sharedStore)

  /* R9-09：按 currentAcademicYearId 过滤的业务数据视图 */
  const currentApplications = computed(() =>
    applications.value.filter((a) => a.academicYearId === currentAcademicYearId.value),
  )

  const currentAdmissions = computed(() =>
    admissions.value.filter((a) => a.academicYearId === currentAcademicYearId.value),
  )

  const currentAnnouncements = computed(() =>
    announcements.value.filter((a) => a.academicYearId === currentAcademicYearId.value),
  )

  return {
    currentAcademicYearId,
    currentApplications,
    currentAdmissions,
    currentAnnouncements,
  }
}
