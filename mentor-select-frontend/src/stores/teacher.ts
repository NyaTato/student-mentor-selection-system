import { defineStore } from 'pinia'
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import {
  SystemState,
  AssignmentSource,
  UserRole,
  type TeacherInfo,
  type StudentInfo,
} from '@/types'
import { useSharedStore } from './shared'
import { useAuthStore } from './auth'
import { useAcademicYearFilter } from '@/composables/useAcademicYearFilter'
import { approveApplicationApi, rejectApplicationApi, revokeApprovalApi, updateTeacherApi } from '@/api/write-api'
import { refreshApplications, refreshAdmissions, refreshTeachers } from '@/api/data-loader'

export const useTeacherStore = defineStore('teacher', () => {
  const sharedStore = useSharedStore()
  const authStore = useAuthStore()
  const { systemState, applications, admissions, students, teachers } =
    storeToRefs(sharedStore)

  /* R9-10：导师仅可见当前 ACTIVE 学年的业务数据 */
  const { currentApplications, currentAdmissions } = useAcademicYearFilter()

  /* 当前登录导师 ID — 从 authStore 动态读取，支持多账号切换 */
  const currentTeacherId = computed(() =>
    authStore.user?.role === UserRole.TEACHER ? authStore.user.id : 101,
  )

  /* 当前导师 — 从共享 store 动态读取，保证跨标签页同步 */
  const currentTeacher = computed<TeacherInfo>(
    () =>
      sharedStore.teachers.find((t) => t.id === currentTeacherId.value) ??
      sharedStore.teachers[0],
  )

  /* 申请我的学生列表 */
  const myApplications = computed(() =>
    currentApplications.value.filter((app) => app.teacherId === currentTeacher.value.id),
  )

  /* 已录取学生列表 */
  const myAdmissions = computed(() =>
    currentAdmissions.value.filter((adm) => adm.teacherId === currentTeacher.value.id),
  )

  /* 名额信息 */
  const quotaInfo = computed(() => ({
    max: currentTeacher.value.maxQuota,
    admitted: currentTeacher.value.currentAdmitted,
    remaining: currentTeacher.value.maxQuota - currentTeacher.value.currentAdmitted,
  }))

  /* 获取学生信息 */
  function getStudentById(id: number): StudentInfo | undefined {
    return students.value.find((s) => s.id === id)
  }

  /* 录取学生 */
  async function admitStudent(applicationId: number): Promise<boolean> {
    /* R2-04：仅在导师筛选阶段允许录取 */
    if (systemState.value !== SystemState.TEACHER_REVIEW) return false
    const app = applications.value.find((a) => a.id === applicationId)
    if (!app) return false
    if (app.teacherId !== currentTeacher.value.id) return false

    /* R2-01 / R2-05：录取前校验名额是否已满 */
    if (currentTeacher.value.currentAdmitted >= currentTeacher.value.maxQuota) return false

    try {
      await approveApplicationApi(applicationId)
      /* 写入成功 → 用服务端数据覆盖本地（server authority），无乐观更新。
       * 名额必须来自汇总目录：角色裁剪后的录取列表算不出全局剩余名额。 */
      const yearId = sharedStore.currentAcademicYearId
      const [freshApplications, freshAdmissions, freshTeachers] = await Promise.all([
        refreshApplications(yearId),
        refreshAdmissions(yearId),
        refreshTeachers(yearId),
      ])
      applications.value = freshApplications
      admissions.value = freshAdmissions
      teachers.value = freshTeachers as typeof teachers.value
      return true
    } catch {
      /* 错误已由 http 拦截器提示 */
      return false
    }
  }

  /* 拒绝学生 */
  async function rejectStudent(applicationId: number): Promise<boolean> {
    /* R2-04：仅在导师筛选阶段允许拒绝 */
    if (systemState.value !== SystemState.TEACHER_REVIEW) return false
    const app = applications.value.find((a) => a.id === applicationId)
    if (!app) return false
    if (app.teacherId !== currentTeacher.value.id) return false

    try {
      await rejectApplicationApi(applicationId)
      /* 拒绝不产生录取，只刷新申请列表（不重复请求其它模块） */
      applications.value = await refreshApplications(sharedStore.currentAcademicYearId)
      return true
    } catch {
      /* 错误已由 http 拦截器提示 */
      return false
    }
  }

  /* 撤销第一轮录取：服务端更新申请并精确释放名额，然后重读权威数据。 */
  async function revokeAdmission(admissionId: number): Promise<boolean> {
    if (systemState.value !== SystemState.TEACHER_REVIEW) return false
    const admission = currentAdmissions.value.find((a) => a.id === admissionId)
    if (!admission || admission.teacherId !== currentTeacher.value.id) return false
    if (admission.source !== AssignmentSource.ROUND1 || admission.applicationId === null) return false

    try {
      await revokeApprovalApi(admission.applicationId)
      const yearId = sharedStore.currentAcademicYearId
      const [freshApplications, freshAdmissions, freshTeachers] = await Promise.all([
        refreshApplications(yearId),
        refreshAdmissions(yearId),
        refreshTeachers(yearId),
      ])
      applications.value = freshApplications
      admissions.value = freshAdmissions
      teachers.value = freshTeachers as typeof teachers.value
      return true
    } catch {
      /* 拒绝原因由 HTTP 层展示；不伪造本地撤销。 */
      return false
    }
  }

  /* 更新导师信息 — v2 用 teacher_id（teacherPk），非 user_id */
  async function updateProfile(
    data: Partial<
      Pick<
        TeacherInfo,
        | 'researchArea'
        | 'profile'
        | 'projectDirection'
        | 'researchTopics'
        | 'requirements'
      >
    >,
  ): Promise<boolean> {
    const teacherPk = currentTeacher.value.teacherPk
    if (!teacherPk) {
      return false
    }
    /* 前端字段名 → 后端字段名 */
    const mappedData: {
      research_area?: string
      profile?: string
      graduation_direction?: string
      thesis_topic?: string
      student_requirement?: string
    } = {}
    if (data.researchArea !== undefined) mappedData.research_area = data.researchArea
    if (data.profile !== undefined) mappedData.profile = data.profile
    if (data.projectDirection !== undefined) mappedData.graduation_direction = data.projectDirection
    if (data.researchTopics !== undefined) mappedData.thesis_topic = data.researchTopics
    if (data.requirements !== undefined) mappedData.student_requirement = data.requirements

    try {
      await updateTeacherApi(teacherPk, mappedData)
      /* 刷新导师数据 — 传入当前学年 ID，避免去年的录取数计入今年的名额 */
      teachers.value = (await refreshTeachers(
        sharedStore.currentAcademicYearId,
      )) as typeof teachers.value
      return true
    } catch {
      /* 错误已由 http 拦截器提示 */
      return false
    }
  }

  return {
    currentTeacher,
    systemState,
    /* R9-10：导师仅可见当前 ACTIVE 学年的业务数据 */
    applications: currentApplications,
    admissions: currentAdmissions,
    students,
    teachers,
    myApplications,
    myAdmissions,
    quotaInfo,
    getStudentById,
    admitStudent,
    rejectStudent,
    revokeAdmission,
    updateProfile,
  }
})
