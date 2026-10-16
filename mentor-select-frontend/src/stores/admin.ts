import { defineStore } from 'pinia'
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import {
  SystemState,
  UserRole,
  ApplicationStatus,
  AccountStatus,
  LogType,
  AutoAssignmentStatus,
  ImportTaskStatus,
  ImportRowStatus,
  type StudentInfo,
  type TeacherInfo,
  type AdminInfo,
  type Announcement,
  type LogEntry,
  type ImportTask,
  type ImportLog,
  type SystemStateSchedule,
} from '@/types'
import { useSharedStore } from './shared'
import { useAuthStore } from './auth'
import { useAcademicYearFilter } from '@/composables/useAcademicYearFilter'
import {
  forwardStateApi,
  rollbackStateApi,
  updateScheduleApi,
  toggleAutoScheduleApi,
  createAnnouncementApi,
  updateAnnouncementApi,
  publishAnnouncementApi,
  unpublishAnnouncementApi,
  deleteAnnouncementApi,
  createStudentApi,
  updateStudentApi,
  deleteStudentApi,
  createTeacherApi,
  updateTeacherApi,
  deleteTeacherApi,
  createAdminApi,
  updateAdminApi,
  deleteAdminApi,
  disableUserApi,
  enableUserApi,
  batchSetQuotaApi,
  manualAssignApi,
  runAutoAssignApi,
  revokeAutoAssignApi,
  createAcademicYearApi,
  activateAcademicYearApi,
  closeAcademicYearApi,
  type UpdateScheduleBody,
} from '@/api/write-api'
import {
  refreshSystemState,
  refreshStudents,
  refreshTeachers,
  refreshAdmins,
  refreshAnnouncements,
  refreshAdmissions,
  refreshAutoAssignmentLogs,
  refreshTeacherDirectory,
} from '@/api/data-loader'

export const useAdminStore = defineStore('admin', () => {
  const sharedStore = useSharedStore()
  /* 角色显式传给加载器（避免 shared store 反向 import auth store 形成循环依赖） */
  const authStore = useAuthStore()
  const {
    systemState,
    currentAcademicYearId,
    academicYears,
    systemStateSchedule,
    stateHistory,
    autoAssignmentLogs,
    importTasks,
    importLogs,
    students,
    teachers,
    admins,
    applications,
    admissions,
    announcements,
    logs,
  } = storeToRefs(sharedStore)

  /* R9-09：按 currentAcademicYearId 过滤的业务数据视图 */
  const {
    currentApplications,
    currentAdmissions,
    currentAnnouncements,
  } = useAcademicYearFilter()

  /* ========== 系统状态（PROJECT.md 4.1 — 6 状态） ========== */
  const stateLabel: Record<SystemState, string> = {
    [SystemState.INIT]: '未开启',
    [SystemState.FIRST_ROUND_OPEN]: '第一轮填报中',
    [SystemState.TEACHER_REVIEW]: '导师筛选阶段',
    [SystemState.SECOND_ROUND_OPEN]: '第二轮报名中',
    [SystemState.AUTO_ASSIGN]: '自动分配中',
    [SystemState.FINISHED]: '结束',
  }

  const currentStateLabel = computed(() => stateLabel[systemState.value])

  /* 状态推进顺序（PROJECT.md 4.2 — 含 AUTO_ASSIGN） */
  const stateOrder: SystemState[] = [
    SystemState.INIT,
    SystemState.FIRST_ROUND_OPEN,
    SystemState.TEACHER_REVIEW,
    SystemState.SECOND_ROUND_OPEN,
    SystemState.AUTO_ASSIGN,
    SystemState.FINISHED,
  ]

  const nextState = computed(() => {
    const idx = stateOrder.indexOf(systemState.value)
    if (idx < 0 || idx >= stateOrder.length - 1) return null
    return stateOrder[idx + 1]
  })

  /* 上一状态（PROJECT.md 4.5 — 逐级回退） */
  const previousState = computed(() => {
    const idx = stateOrder.indexOf(systemState.value)
    if (idx <= 0) return null
    return stateOrder[idx - 1]
  })

  const canAdvanceState = computed(() => nextState.value !== null)
  const canRollbackState = computed(() => previousState.value !== null)

  /* ========== 状态推进（PROJECT.md 4.2） ========== */
  async function advanceState(): Promise<boolean> {
    if (!nextState.value) return false
    /* 前置条件校验（PROJECT.md 4.2） */
    if (systemState.value === SystemState.INIT) {
      if (teachers.value.length === 0 || students.value.length === 0) {
        return false
      }
    }
    try {
      await forwardStateApi({ academic_year: currentAcademicYearId.value })
      const yearId = currentAcademicYearId.value
      const { systemState: newState, schedule, history } = await refreshSystemState(yearId)
      systemState.value = newState
      if (schedule) systemStateSchedule.value = schedule
      stateHistory.value = history
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== 状态回退（PROJECT.md 4.5 / R12-01 ~ R12-08） ========== */
  async function rollbackState(reason: string): Promise<boolean> {
    if (!previousState.value) return false
    /* R12-03：回退原因必填，最少 10 字符 */
    if (!reason || reason.trim().length < 10) return false
    try {
      await rollbackStateApi({ academic_year: currentAcademicYearId.value, reason })
      const yearId = currentAcademicYearId.value
      const { systemState: newState, schedule, history } = await refreshSystemState(yearId)
      systemState.value = newState
      if (schedule) systemStateSchedule.value = schedule
      stateHistory.value = history
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== 自动时间切换（PROJECT.md 4.4 / R13-01 ~ R13-08） ========== */
  async function updateSchedule(data: Partial<SystemStateSchedule>): Promise<boolean> {
    try {
      const body: UpdateScheduleBody = {
        academic_year: currentAcademicYearId.value,
      }
      if (data.firstRoundStartAt !== undefined) body.first_round_start_at = data.firstRoundStartAt ?? undefined
      if (data.firstRoundEndAt !== undefined) body.first_round_end_at = data.firstRoundEndAt ?? undefined
      if (data.teacherReviewEndAt !== undefined) body.teacher_review_end_at = data.teacherReviewEndAt ?? undefined
      if (data.secondRoundEndAt !== undefined) body.second_round_end_at = data.secondRoundEndAt ?? undefined
      if (data.autoEnabled !== undefined) body.auto_enabled = data.autoEnabled
      await updateScheduleApi(body)
      const yearId = currentAcademicYearId.value
      const { systemState: newState, schedule, history } = await refreshSystemState(yearId)
      systemState.value = newState
      if (schedule) systemStateSchedule.value = schedule
      stateHistory.value = history
      return true
    } catch (err) {
      return false
    }
  }

  async function toggleAutoSwitch(enabled: boolean): Promise<boolean> {
    try {
      await toggleAutoScheduleApi({ academic_year: currentAcademicYearId.value, enabled })
      const yearId = currentAcademicYearId.value
      const { systemState: newState, schedule, history } = await refreshSystemState(yearId)
      systemState.value = newState
      if (schedule) systemStateSchedule.value = schedule
      stateHistory.value = history
      return true
    } catch (err) {
      return false
    }
  }

  function tickAutoTransition(): boolean {
    return false
  }

  /* ========== 统计数据 ========== */
  const stats = computed(() => ({
    studentCount: students.value.length,
    teacherCount: teachers.value.length,
    adminCount: admins.value.length,
    applicationCount: currentApplications.value.length,
    admissionCount: currentAdmissions.value.length,
    pendingApplicationCount: currentApplications.value.filter(
      (a) => a.status === ApplicationStatus.PENDING,
    ).length,
    unmatchedStudentCount: getUnmatchedStudents().length,
    publishedAnnouncementCount: currentAnnouncements.value.filter((a) => a.published).length,
  }))

  /* 未匹配学生 — 第二轮结束后仍无录取记录的学生（仅当前学年） */
  function getUnmatchedStudents(): StudentInfo[] {
    const admittedIds = new Set(currentAdmissions.value.map((a) => a.studentId))
    return students.value.filter((s) => !admittedIds.has(s.id))
  }

  const unmatchedStudents = computed(() => getUnmatchedStudents())

  /* ========== 学生管理（v2 — 一次性创建 User + Student，password 必填） ========== */
  async function addStudent(
    data: Omit<StudentInfo, 'id' | 'role'> & { password: string },
  ): Promise<{ success: boolean; generatedPassword?: string | null }> {
    try {
      await createStudentApi({
        username: data.username,
        password: data.password,
        student_number: data.studentId,
        name: data.name,
        major: data.major,
        class_name: data.grade || '',
        department: data.department,
        phone: data.phone,
      })
      students.value = (await refreshStudents()).map((s) => ({
        ...s,
        status: AccountStatus.ACTIVE,
      }))
      return { success: true, generatedPassword: null }
    } catch (err) {
      return { success: false }
    }
  }

  async function updateStudent(id: number, data: Partial<StudentInfo>): Promise<boolean> {
    try {
      const student = students.value.find((s) => s.id === id)
      if (!student?.studentPk) {
        return false
      }
      await updateStudentApi(student.studentPk, {
        name: data.name,
        major: data.major,
        class_name: data.grade,
        department: data.department,
      })
      students.value = (await refreshStudents()).map((s) => ({
        ...s,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  /* R5-03 / BC-07：已关联申请或录取记录的账号不允许物理删除，只能禁用 */
  async function deleteStudent(id: number): Promise<boolean> {
    /* hasData 信息性检查 — 后端决定是否物理删除或禁用 */
    const hasData =
      applications.value.some((a) => a.studentId === id) ||
      admissions.value.some((a) => a.studentId === id)
    if (hasData) {
    }
    try {
      const student = students.value.find((s) => s.id === id)
      if (!student?.studentPk) {
        return false
      }
      await deleteStudentApi(student.studentPk)
      students.value = (await refreshStudents()).map((s) => ({
        ...s,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  async function toggleStudentStatus(id: number, status: AccountStatus): Promise<boolean> {
    try {
      if (status === AccountStatus.DISABLED) {
        await disableUserApi(id)
      } else {
        await enableUserApi(id)
      }
      students.value = (await refreshStudents()).map((s) => ({
        ...s,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== 导师管理（v2 — 一次性创建 User + Teacher，password 必填） ========== */
  async function addTeacher(
    data: Omit<TeacherInfo, 'id' | 'role'> & { password: string },
  ): Promise<{ success: boolean; generatedPassword?: string | null }> {
    try {
      await createTeacherApi({
        username: data.username,
        password: data.password,
        teacher_number: data.teacherNumber,
        name: data.name,
        college: data.department,
        title: data.title,
        research_area: data.researchArea,
        profile: data.profile,
        graduation_direction: data.projectDirection,
        thesis_topic: data.researchTopics,
        student_requirement: data.requirements,
      })
      teachers.value = (await refreshTeachers(currentAcademicYearId.value)).map((t) => ({
        ...t,
        status: AccountStatus.ACTIVE,
      }))
      return { success: true, generatedPassword: null }
    } catch (err) {
      return { success: false }
    }
  }

  async function updateTeacher(id: number, data: Partial<TeacherInfo>): Promise<boolean> {
    try {
      const teacher = teachers.value.find((t) => t.id === id)
      if (!teacher?.teacherPk) {
        return false
      }
      await updateTeacherApi(teacher.teacherPk, {
        college: data.department,
        title: data.title,
        research_area: data.researchArea,
        profile: data.profile,
        graduation_direction: data.projectDirection,
        thesis_topic: data.researchTopics,
        student_requirement: data.requirements,
      })
      teachers.value = (await refreshTeachers(currentAcademicYearId.value)).map((t) => ({
        ...t,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  /* 设置招生名额 — BC-03：名额硬约束，校验层强制保证不低于已录取人数（保留 v1） */
  async function setTeacherQuota(id: number, maxQuota: number): Promise<boolean> {
    try {
      await batchSetQuotaApi({
        academic_year: currentAcademicYearId.value,
        quotas: [{ teacher_id: id, max_quota: maxQuota }],
      })
      teachers.value = (await refreshTeachers(currentAcademicYearId.value)).map((t) => ({
        ...t,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  async function deleteTeacher(id: number): Promise<boolean> {
    /* hasData 信息性检查 — 后端决定是否物理删除或禁用 */
    const hasData =
      applications.value.some((a) => a.teacherId === id) ||
      admissions.value.some((a) => a.teacherId === id)
    if (hasData) {
    }
    try {
      const teacher = teachers.value.find((t) => t.id === id)
      if (!teacher?.teacherPk) {
        return false
      }
      await deleteTeacherApi(teacher.teacherPk)
      teachers.value = (await refreshTeachers(currentAcademicYearId.value)).map((t) => ({
        ...t,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }

  async function toggleTeacherStatus(id: number, status: AccountStatus): Promise<boolean> {
    try {
      if (status === AccountStatus.DISABLED) {
        await disableUserApi(id)
      } else {
        await enableUserApi(id)
      }
      teachers.value = (await refreshTeachers(currentAcademicYearId.value)).map((t) => ({
        ...t,
        status: AccountStatus.ACTIVE,
      }))
      return true
    } catch (err) {
      return false
    }
  }


  /* ========== 管理员管理（v2 — 一次性创建 User + Admin，password 必填） ========== */
  async function addAdmin(
    data: Omit<AdminInfo, 'id' | 'role'> & { password: string },
  ): Promise<{ success: boolean; generatedPassword?: string | null }> {
    try {
      await createAdminApi({
        username: data.username,
        password: data.password,
        name: data.name,
      })
      admins.value = await refreshAdmins()
      return { success: true, generatedPassword: null }
    } catch (err) {
      return { success: false }
    }
  }

  async function updateAdmin(id: number, data: Partial<AdminInfo>): Promise<boolean> {
    try {
      const admin = admins.value.find((a) => a.id === id)
      if (!admin?.adminPk) {
        return false
      }
      await updateAdminApi(admin.adminPk, {
        name: data.name,
      })
      admins.value = await refreshAdmins()
      return true
    } catch (err) {
      return false
    }
  }

  async function deleteAdmin(id: number): Promise<boolean> {
    try {
      const admin = admins.value.find((a) => a.id === id)
      if (!admin?.adminPk) {
        return false
      }
      await deleteAdminApi(admin.adminPk)
      admins.value = await refreshAdmins()
      return true
    } catch (err) {
      return false
    }
  }


  /* ========== 公告管理（R7-01 ~ R7-04） ========== */
  async function addAnnouncement(data: {
    title: string
    content: string
    published?: boolean
  }): Promise<number> {
    try {
      const res = await createAnnouncementApi({
        academic_year: currentAcademicYearId.value,
        title: data.title,
        content: data.content,
        is_published: data.published ?? false,
      })
      announcements.value = await refreshAnnouncements(currentAcademicYearId.value)
      return res.id ?? 0
    } catch (err) {
      return 0
    }
  }

  async function updateAnnouncement(
    id: number,
    data: Partial<Pick<Announcement, 'title' | 'content'>>,
  ): Promise<boolean> {
    try {
      await updateAnnouncementApi(id, {
        title: data.title,
        content: data.content,
      })
      announcements.value = await refreshAnnouncements(currentAcademicYearId.value)
      return true
    } catch (err) {
      return false
    }
  }

  async function toggleAnnouncementPublish(id: number): Promise<boolean> {
    const ann = announcements.value.find((a) => a.id === id)
    if (!ann) return false
    try {
      if (!ann.published) {
        await publishAnnouncementApi(id)
      } else {
        await unpublishAnnouncementApi(id)
      }
      announcements.value = await refreshAnnouncements(currentAcademicYearId.value)
      return true
    } catch (err) {
      return false
    }
  }

  async function deleteAnnouncement(id: number): Promise<boolean> {
    try {
      await deleteAnnouncementApi(id)
      announcements.value = await refreshAnnouncements(currentAcademicYearId.value)
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== 人工分配（R8-01 ~ R8-05） ========== */

  /**
   * 管理员人工分配 — 服务端权威（server authority）。
   *
   * 旧实现是纯本地的：自己在内存里编一个 admission id、塞进数组、把导师
   * currentAdmitted++，再同步到 localStorage —— 刷新页面（或换台机器）
   * 一切都会消失，属于**伪造成功**：后端的录取表根本没有这条记录。
   *
   * 现在：
   *   1. POST /api/v2/assignments/manual-assign/ 让后端在事务里校验名额并落库；
   *   2. 只有后端返回成功，才从服务端重新拉取录取列表；
   *   3. 导师名额（admitted_count / remaining_quota）同样从服务端**汇总目录**重取 ——
   *      人工分配会占用名额，本地自增无法反映真实剩余。
   *
   * 任何一步失败都不修改本地业务状态（无乐观更新）。
   *
   * @returns 成功与否；失败原因由 http 拦截器提示（如名额已满 / 学生已匹配）
   */
  async function manualAssign(studentId: number, teacherId: number): Promise<boolean> {
    /* R8-03 / R8-02：本地预检只用于「明显的」非法操作提前返回，不作为权威判断
     * （真实约束由后端事务 + 唯一索引保证，避免前端重复提交造成的竞态）。 */
    /* 与 unmatchedStudents 使用同一「当前学年」视图，避免跨学年误判 */
    const isUnmatched = !currentAdmissions.value.some((a) => a.studentId === studentId)
    if (!isUnmatched) return false

    const teacher = teachers.value.find((t) => t.id === teacherId)
    if (!teacher) return false
    if (teacher.currentAdmitted >= teacher.maxQuota) return false

    const yearId = currentAcademicYearId.value
    if (!yearId) return false

    try {
      await manualAssignApi({
        academic_year: yearId,
        student: studentId,
        teacher: teacherId,
      })
    } catch {
      /* 错误已由 http 拦截器提示；本地状态保持不变 */
      return false
    }

    /* 写入成功 → 用服务端数据覆盖本地（server authority） */
    const [freshAdmissions, directory] = await Promise.all([
      refreshAdmissions(yearId),
      refreshTeacherDirectory(yearId),
    ])
    admissions.value = freshAdmissions

    /* 导师名额以服务端汇总值为准；拿不到汇总的导师保持原值不动 */
    teachers.value = teachers.value.map((t) => {
      const agg = directory.get(t.id)
      if (!agg) return t
      return {
        ...t,
        maxQuota: agg.max_quota ?? 0,
        currentAdmitted: agg.admitted_count,
      }
    })

    return true
  }

  /* ========== 自动分配（PROJECT.md 3.5 / R10-01 ~ R10-11） ========== */

  /* 预览自动分配：返回预计可分配数量 + 前 5 名可分配导师 */
  const autoAssignPreview = computed(() => {
    const unmatched = getUnmatchedStudents()
    /* R10-03：按剩余名额降序；R10-04：名额相同按 teacher_number 升序 */
    const sorted = teachers.value
      .filter((t) => t.status === AccountStatus.ACTIVE && t.currentAdmitted < t.maxQuota)
      .map((t) => ({
        id: t.id,
        name: t.name,
        teacherNumber: t.teacherNumber,
        department: t.department,
        title: t.title,
        remaining: t.maxQuota - t.currentAdmitted,
        maxQuota: t.maxQuota,
        currentAdmitted: t.currentAdmitted,
      }))
      .sort((a, b) => b.remaining - a.remaining || a.teacherNumber.localeCompare(b.teacherNumber))

    const totalRemaining = sorted.reduce((sum, t) => sum + t.remaining, 0)
    return {
      totalCandidates: unmatched.length,
      assignableCount: Math.min(unmatched.length, totalRemaining),
      totalRemaining,
      isInsufficient: totalRemaining < unmatched.length,
      topTeachers: sorted.slice(0, 5),
      allTeachers: sorted,
    }
  })

  /* R10-10：并发控制 — 同一学年同时仅能有一个自动分配任务运行 */
  const isAutoAssignRunning = computed(
    () =>
      autoAssignmentLogs.value.some(
        (l) =>
          l.academicYearId === currentAcademicYearId.value &&
          l.status === AutoAssignmentStatus.RUNNING,
      ),
  )

  /* 执行自动分配（R10-01 ~ R10-11） */
  async function executeAutoAssign(): Promise<{
    success: boolean
    logId: number | null
    message: string
  }> {
    if (isAutoAssignRunning.value) {
      return { success: false, logId: null, message: '已有自动分配任务正在运行' }
    }
    const preview = autoAssignPreview.value
    if (preview.totalCandidates === 0) {
      return { success: false, logId: null, message: '没有未匹配学生需要分配' }
    }
    try {
      const res = await runAutoAssignApi({
        academic_year: currentAcademicYearId.value,
      })
      const yearId = currentAcademicYearId.value
      admissions.value = await refreshAdmissions(yearId)
      autoAssignmentLogs.value = await refreshAutoAssignmentLogs(yearId)
      const { systemState: newState, schedule, history } = await refreshSystemState(yearId)
      systemState.value = newState
      if (schedule) systemStateSchedule.value = schedule
      stateHistory.value = history
      const logId = res.log_id ?? null
      const assigned = res.assigned_count ?? 0
      const failed = res.failed_count ?? 0
      return {
        success: true,
        logId,
        message: `自动分配完成：成功 ${assigned} 人，失败 ${failed} 人`,
      }
    } catch (err) {
      return { success: false, logId: null, message: '自动分配执行失败' }
    }
  }

  /* R10-08：撤销整批自动分配 */
  async function revokeAutoAssign(logId: number): Promise<boolean> {
    try {
      await revokeAutoAssignApi({
        academic_year: currentAcademicYearId.value,
        auto_assignment_log: logId,
      })
      const yearId = currentAcademicYearId.value
      admissions.value = await refreshAdmissions(yearId)
      autoAssignmentLogs.value = await refreshAutoAssignmentLogs(yearId)
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== 学年管理（PROJECT.md 13 / R9-01 ~ R9-12） ========== */
  const currentAcademicYear = computed(
    () => academicYears.value.find((y) => y.id === currentAcademicYearId.value) ?? null,
  )

  /* R9-03：同时仅能有一个 ACTIVE 学年 */
  async function createAcademicYear(name: string): Promise<boolean> {
    /* R9-01：学年格式 YYYY-YYYY，结束年份 = 开始年份 + 1 */
    const match = /^(\d{4})-(\d{4})$/.exec(name)
    if (!match) return false
    const startYear = Number(match[1])
    const endYear = Number(match[2])
    if (endYear !== startYear + 1) return false
    try {
      await createAcademicYearApi({ name, start_year: startYear, end_year: endYear })
      await sharedStore.loadFromServer(authStore.user?.role ?? null)
      return true
    } catch (err) {
      return false
    }
  }

  /* R9-04 / R9-06：激活学年，前置 = 当前无 ACTIVE 或当前 ACTIVE = FINISHED */
  async function activateAcademicYear(id: number): Promise<boolean> {
    try {
      await activateAcademicYearApi(id)
      currentAcademicYearId.value = id
      await sharedStore.loadFromServer(authStore.user?.role ?? null)
      return true
    } catch (err) {
      return false
    }
  }

  /* R9-05：关闭学年，前置 = system_state = FINISHED */
  async function closeAcademicYear(id: number): Promise<boolean> {
    try {
      await closeAcademicYearApi(id)
      await sharedStore.loadFromServer(authStore.user?.role ?? null)
      return true
    } catch (err) {
      return false
    }
  }

  /* 切换当前查看的学年（管理员查看历史学年数据，只读） */
  async function switchAcademicYear(id: number): Promise<boolean> {
    const year = academicYears.value.find((y) => y.id === id)
    if (!year) return false
    try {
      currentAcademicYearId.value = id
      await sharedStore.loadFromServer(authStore.user?.role ?? null)
      return true
    } catch (err) {
      return false
    }
  }

  /* ========== Excel 导入（PROJECT.md 7.13 / R11-01 ~ R11-10） ========== */
  /* R11-07：异步处理，立即返回任务 ID */
  function createImportTask(
    role: UserRole,
    fileName: string,
    fileSize: number,
    rows: Array<Record<string, string>>,
  ): number {
    const id = Math.max(0, ...importTasks.value.map((t) => t.id)) + 1
    const now = new Date().toISOString()
    /* 同步处理 Mock — 实际后端会异步 */
    let successCount = 0
    let failureCount = 0
    const newLogs: ImportLog[] = []
    rows.forEach((row, idx) => {
      const logId = Math.max(0, ...importLogs.value.map((l) => l.id)) + 1 + idx
      const username = row.username ?? ''
      /* R11-06：重复 username 跳过 */
      const exists =
        students.value.some((s) => s.username === username) ||
        teachers.value.some((t) => t.username === username) ||
        admins.value.some((a) => a.username === username)
      if (exists || !username) {
        failureCount++
        newLogs.push({
          id: logId,
          taskId: id,
          rowNumber: idx + 1,
          rowData: JSON.stringify(row),
          status: ImportRowStatus.FAILED,
          failReason: !username ? '用户名不能为空' : `用户名 ${username} 已存在，跳过该行`,
          createdAt: now,
        })
        return
      }
      /* 实际写入 */
      if (role === UserRole.STUDENT) {
        const newId = Math.max(0, ...students.value.map((s) => s.id)) + 1
        students.value.push({
          id: newId,
          username,
          name: row.name ?? '',
          role: UserRole.STUDENT,
          studentId: row.studentId ?? username,
          major: row.major ?? '',
          grade: row.grade ?? '',
          department: row.department ?? '',
          phone: row.phone ?? '',
          status: AccountStatus.ACTIVE,
        })
      } else if (role === UserRole.TEACHER) {
        const newId = Math.max(100, ...teachers.value.map((t) => t.id)) + 1
        teachers.value.push({
          id: newId,
          username,
          name: row.name ?? '',
          role: UserRole.TEACHER,
          teacherNumber: row.teacherNumber ?? `T${Date.now()}`,
          department: row.department ?? '',
          title: row.title ?? '',
          researchArea: row.researchArea ?? '',
          profile: '',
          maxQuota: Number(row.maxQuota ?? 0),
          currentAdmitted: 0,
          projectDirection: '',
          researchTopics: '',
          requirements: '',
          status: AccountStatus.ACTIVE,
        })
      } else {
        const newId = Math.max(0, ...admins.value.map((a) => a.id)) + 1
        admins.value.push({
          id: newId,
          username,
          name: row.name ?? '',
          role: UserRole.ADMIN,
          createdAt: now,
          lastLoginAt: undefined,
        })
      }
      successCount++
      newLogs.push({
        id: logId,
        taskId: id,
        rowNumber: idx + 1,
        rowData: JSON.stringify(row),
        status: ImportRowStatus.SUCCESS,
        failReason: null,
        createdAt: now,
      })
    })

    const task: ImportTask = {
      id,
      academicYearId: currentAcademicYearId.value,
      role,
      fileName,
      fileSize,
      status:
        failureCount === 0
          ? ImportTaskStatus.COMPLETED
          : successCount === 0
            ? ImportTaskStatus.FAILED
            : ImportTaskStatus.PARTIALLY_COMPLETED,
      totalRows: rows.length,
      successCount,
      failureCount,
      operatorId: 1,
      operatorName: '系统管理员',
      createdAt: now,
      completedAt: now,
    }
    importTasks.value.unshift(task)
    importLogs.value.push(...newLogs)
    addLog(
      LogType.OPERATION,
      'admin',
      `Excel 导入${role === UserRole.STUDENT ? '学生' : role === UserRole.TEACHER ? '导师' : '管理员'}`,
      `成功 ${successCount} / 失败 ${failureCount}`,
    )
    return id
  }

  function getImportLogsByTask(taskId: number): ImportLog[] {
    return importLogs.value.filter((l) => l.taskId === taskId)
  }

  /* 有剩余名额的导师 */
  const availableTeachers = computed(() =>
    teachers.value
      .filter((t) => t.status === AccountStatus.ACTIVE && t.currentAdmitted < t.maxQuota)
      .map((t) => ({
        id: t.id,
        name: t.name,
        department: t.department,
        title: t.title,
        remaining: t.maxQuota - t.currentAdmitted,
        maxQuota: t.maxQuota,
        currentAdmitted: t.currentAdmitted,
      })),
  )

  /* ========== 分配结果（R9-09：仅当前学年） ========== */
  const assignmentResults = computed(() =>
    currentAdmissions.value.map((adm) => {
      const student = students.value.find((s) => s.id === adm.studentId)
      const teacher = teachers.value.find((t) => t.id === adm.teacherId)
      return {
        admissionId: adm.id,
        studentId: adm.studentId,
        studentName: student?.name ?? '未知',
        studentNumber: student?.studentId ?? '-',
        major: student?.major ?? '-',
        department: student?.department ?? '-',
        teacherId: adm.teacherId,
        teacherName: teacher?.name ?? '未知',
        teacherDepartment: teacher?.department ?? '-',
        source: adm.source,
        assignedAt: adm.createdAt,
      }
    }),
  )

  /* ========== 日志 ========== */
  /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
  function addLog(..._args: unknown[]) {
    /* 后端自动记录日志，此函数保留为 no-op 接口兼容 */
  }

  function getLogs(filter?: { type?: LogType }): LogEntry[] {
    if (!filter?.type) return logs.value
    return logs.value.filter((l) => l.type === filter.type)
  }

  /* 重置演示数据 */
  function resetDemo() {
    sharedStore.reset()
  }

  return {
    /* state */
    systemState,
    currentAcademicYearId,
    academicYears,
    systemStateSchedule,
    stateHistory,
    autoAssignmentLogs,
    importTasks,
    importLogs,
    students,
    teachers,
    admins,
    announcements,
    applications,
    admissions,
    logs,
    /* R9-09：按 currentAcademicYearId 过滤的业务数据视图 */
    currentApplications,
    currentAdmissions,
    currentAnnouncements,
    /* computed */
    currentStateLabel,
    nextState,
    previousState,
    canAdvanceState,
    canRollbackState,
    currentAcademicYear,
    isAutoAssignRunning,
    autoAssignPreview,
    stats,
    unmatchedStudents,
    availableTeachers,
    assignmentResults,
    /* state metadata */
    stateLabel,
    stateOrder,
    /* system state */
    advanceState,
    rollbackState,
    updateSchedule,
    toggleAutoSwitch,
    tickAutoTransition,
    /* students */
    addStudent,
    updateStudent,
    deleteStudent,
    toggleStudentStatus,
    /* teachers */
    addTeacher,
    updateTeacher,
    setTeacherQuota,
    deleteTeacher,
    toggleTeacherStatus,
    /* admins */
    addAdmin,
    updateAdmin,
    deleteAdmin,
    /* announcements */
    addAnnouncement,
    updateAnnouncement,
    toggleAnnouncementPublish,
    deleteAnnouncement,
    /* manual assignment */
    manualAssign,
    /* auto assignment */
    executeAutoAssign,
    revokeAutoAssign,
    /* academic year */
    createAcademicYear,
    activateAcademicYear,
    closeAcademicYear,
    switchAcademicYear,
    /* excel import */
    createImportTask,
    getImportLogsByTask,
    /* logs */
    addLog,
    getLogs,
    /* demo */
    resetDemo,
  }
})
