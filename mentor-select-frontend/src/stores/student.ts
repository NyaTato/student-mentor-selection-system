import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import {
  SystemState,
  ApplicationStatus,
  StudentStatus,
  AssignmentSource,
  UserRole,
  type TeacherInfo,
  type HistoryEntry,
} from '@/types'
import { useSharedStore } from './shared'
import { useAuthStore } from './auth'
import { useAcademicYearFilter } from '@/composables/useAcademicYearFilter'
import { submitApplicationApi, cancelApplicationApi, updateStudentPhoneApi } from '@/api/write-api'
import { refreshApplications } from '@/api/data-loader'

export const useStudentStore = defineStore('student', () => {
  const sharedStore = useSharedStore()
  const authStore = useAuthStore()
  const { systemState, applications, teachers } = storeToRefs(sharedStore)

  /* R9-10：学生仅可见当前 ACTIVE 学年的业务数据 */
  const {
    currentApplications,
    currentAdmissions,
    currentAnnouncements,
  } = useAcademicYearFilter()

  /* 当前登录学生 ID — 从 authStore 动态读取，支持多账号切换 */
  const currentStudentId = computed(() =>
    authStore.user?.role === UserRole.STUDENT ? authStore.user.id : 1,
  )

  /* 当前学生 — 从共享 store（当前标签页内存，服务端权威数据）动态读取 */
  const currentStudent = computed(
    () =>
      sharedStore.students.find((s) => s.id === currentStudentId.value) ??
      sharedStore.students[0],
  )

  /* 历史记录 — 从申请和录取记录推导 */
  const history = ref<HistoryEntry[]>([])

  /* 当前学生的第一轮申请 */
  const myFirstRoundApplication = computed(() =>
    currentApplications.value.find((app) => app.studentId === currentStudent.value.id && app.round === 1),
  )

  /* 当前学生的第二轮申请 */
  const mySecondRoundApplication = computed(() =>
    currentApplications.value.find((app) => app.studentId === currentStudent.value.id && app.round === 2),
  )

  /* 当前学生的录取记录 */
  const myAdmission = computed(() =>
    currentAdmissions.value.find((adm) => adm.studentId === currentStudent.value.id),
  )

  /* 学生个人状态 — 对应 PROJECT.md 5.2 六种状态 */
  const studentStatus = computed<StudentStatus>(() => {
    if (systemState.value === SystemState.INIT) return StudentStatus.NOT_SUBMITTED

    if (systemState.value === SystemState.FIRST_ROUND_OPEN) {
      /* 第一轮开放期：已提交申请 → 待审核；未提交 → 未填报 */
      if (myFirstRoundApplication.value) return StudentStatus.WAITING_REVIEW
      return StudentStatus.NOT_SUBMITTED
    }

    if (systemState.value === SystemState.TEACHER_REVIEW) {
      if (myFirstRoundApplication.value) return StudentStatus.WAITING_REVIEW
      return StudentStatus.NOT_SUBMITTED
    }

    if (systemState.value === SystemState.SECOND_ROUND_OPEN) {
      const app = myFirstRoundApplication.value
      if (app?.status === ApplicationStatus.ACCEPTED) return StudentStatus.ACCEPTED
      return StudentStatus.REJECTED
    }

    if (systemState.value === SystemState.FINISHED) {
      if (myAdmission.value) {
        if (myAdmission.value.source === AssignmentSource.MANUAL) {
          return StudentStatus.WAITING_ASSIGNMENT
        }
        return StudentStatus.ROUND2_MATCHED
      }
      return StudentStatus.WAITING_ASSIGNMENT
    }

    return StudentStatus.NOT_SUBMITTED
  })

  /* 是否第一轮被拒（可参加第二轮） */
  const isRejectedInRound1 = computed(() => {
    const app = myFirstRoundApplication.value
    return app?.status === ApplicationStatus.REJECTED
  })

  /* 是否第一轮已录取 */
  const isAcceptedInRound1 = computed(() => {
    const app = myFirstRoundApplication.value
    return app?.status === ApplicationStatus.ACCEPTED
  })

  /* 获取导师详情 */
  function getTeacherById(id: number): TeacherInfo | undefined {
    return teachers.value.find((t) => t.id === id)
  }

  /* 提交第一轮申请 — 调用真实 API */
  async function submitFirstRoundApplication(teacherId: number): Promise<void> {
    /* R1-01：仅在第一轮报名开放阶段允许提交/修改 */
    if (systemState.value !== SystemState.FIRST_ROUND_OPEN) return
    await submitApplicationApi({
      academic_year: sharedStore.currentAcademicYearId,
      teacher: teacherId,
      round: 1,
    })
    /* 刷新申请数据 */
    try {
      applications.value = await refreshApplications(sharedStore.currentAcademicYearId)
    } catch {
      /* ignore */
    }
    const teacher = getTeacherById(teacherId)
    history.value.push({
      id: history.value.length + 1,
      round: '第一轮',
      teacherName: teacher?.name || '未知',
      status: '待筛选',
      action: '提交志愿',
      timestamp: new Date().toISOString(),
    })
  }

  /* R3-02: 提交第二轮申请 — 先到先得，后端立即创建 admission 占用名额 */
  async function submitSecondRoundApplication(
    teacherId: number,
  ): Promise<{ success: boolean; message: string }> {
    /* R3-01：仅在第二轮报名开放阶段允许选择导师 */
    if (systemState.value !== SystemState.SECOND_ROUND_OPEN) {
      return { success: false, message: '当前不在第二轮报名阶段' }
    }
    /* R3-05：第二轮每位学生只能选择一位导师 */
    if (mySecondRoundApplication.value) {
      return { success: false, message: '您已在第二轮选择了导师' }
    }
    /* R3-02：第一轮已录取的学生不可参加第二轮 */
    if (isAcceptedInRound1.value) {
      return { success: false, message: '您已在第一轮被录取，无需参加第二轮' }
    }
    const teacher = getTeacherById(teacherId)
    if (!teacher) return { success: false, message: '导师不存在' }

    try {
      await submitApplicationApi({
        academic_year: sharedStore.currentAcademicYearId,
        teacher: teacherId,
        round: 2,
      })
      /* 写入成功 → 从服务端重新拉取（server authority）。
       * 第二轮提交会立即占用名额，因此必须整轮刷新（申请 + 录取 + 导师汇总名额），
       * 不再额外单独请求 applications（那会重复一次同样的请求）。 */
      try {
        await sharedStore.loadFromServer(authStore.user?.role ?? null)
      } catch {
        /* ignore */
      }
      const teacherName = teacher.name
      history.value.push({
        id: history.value.length + 1,
        round: '第二轮',
        teacherName,
        status: '已录取',
        action: '提交志愿',
        timestamp: new Date().toISOString(),
      })
      return { success: true, message: '申请成功，已占用一个名额' }
    } catch {
      /* 错误已由 http 拦截器提示 */
      return { success: false, message: '提交失败，请稍后重试' }
    }
  }

  /* R3-06: 取消第二轮申请 — 释放名额，允许重新选择其他导师 */
  async function cancelSecondRoundApplication(): Promise<{ success: boolean; message: string }> {
    const app = mySecondRoundApplication.value
    if (!app) {
      return { success: false, message: '您没有第二轮申请可取消' }
    }
    try {
      await cancelApplicationApi(app.id)
      /* 刷新数据 — R3-07: 取消后释放名额（同样整轮刷新，避免重复请求） */
      try {
        await sharedStore.loadFromServer(authStore.user?.role ?? null)
      } catch {
        /* ignore */
      }
      return { success: true, message: '取消成功，名额已释放' }
    } catch {
      return { success: false, message: '取消失败，请稍后重试' }
    }
  }

  async function updatePhone(phone: string): Promise<void> {
    /* 调用 v2 后端 API 写入数据库，成功后同步本地缓存 */
    const student = sharedStore.students.find((s) => s.id === currentStudentId.value)
    if (!student?.studentPk) {
      return
    }
    await updateStudentPhoneApi(student.studentPk, { phone })
    /* API 写入成功后再更新本地数据 */
    student.phone = phone
  }

  return {
    currentStudent,
    systemState,
    /* R9-10：学生仅可见当前 ACTIVE 学年的业务数据 */
    applications: currentApplications,
    admissions: currentAdmissions,
    announcements: currentAnnouncements,
    history,
    teachers,
    myFirstRoundApplication,
    mySecondRoundApplication,
    myAdmission,
    studentStatus,
    isRejectedInRound1,
    isAcceptedInRound1,
    getTeacherById,
    submitFirstRoundApplication,
    submitSecondRoundApplication,
    cancelSecondRoundApplication,
    updatePhone,
  }
})
