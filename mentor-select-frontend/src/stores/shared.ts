/**
 * Shared Store — 当前标签页内的共享数据单一源
 *
 * 隐私边界（重要）：
 *   本 store **不持久化、不广播**任何角色数据。
 *   早期版本把全量角色数据（学生/导师/管理员/日志）写进 localStorage
 *   （`mentor-shared-state`）并用 BroadcastChannel 跨标签页同步，导致
 *   同一浏览器里「上一个管理员登录过，下一位学生登录」时能看到管理员的
 *   残留数据（跨账号泄露）。
 *
 *   现在的契约：
 *     1. 数据只存在于**当前标签页的内存**里，刷新页面即从服务端重新拉取；
 *     2. 登录 / 登出 / 切换账号或角色时调用 clear() 清空内存状态；
 *     3. 启动时删除遗留的 localStorage 缓存键（旧版本留下的敏感数据）；
 *     4. 写入操作后从服务端重新读取（server authority），不依赖本地乐观状态；
 *     5. JWT 仍按既有行为存放在 sessionStorage（每标签页独立）。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  SystemState,
  AccountStatus,
  UserRole,
  type StudentInfo,
  type TeacherInfo,
  type AdminInfo,
  type Announcement,
  type Application,
  type Admission,
  type LogEntry,
  type AcademicYear,
  type SystemStateSchedule,
  type StateHistory,
  type AutoAssignmentLog,
  type ImportTask,
  type ImportLog,
} from '@/types'
import { loadAllFromServer } from '@/api/data-loader'

/* 账号扩展 — 学生/导师可禁用启用（R5-03） */
export interface StudentWithStatus extends StudentInfo {
  status: AccountStatus
}
export interface TeacherWithStatus extends TeacherInfo {
  status: AccountStatus
}

/* 旧版本的跨标签页共享缓存键 — 启动时清除，阻止历史敏感数据继续留在浏览器里 */
const LEGACY_STORAGE_KEY = 'mentor-shared-state'

function removeLegacyStorage() {
  try {
    localStorage.removeItem(LEGACY_STORAGE_KEY)
  } catch {
    /* localStorage 不可用（隐私模式等）时忽略 */
  }
}

/* 创建默认初始数据 — 空状态，等待从后端加载 */
function createDefaultState() {
  return {
    systemState: SystemState.INIT,
    currentAcademicYearId: 0,
    academicYears: [] as AcademicYear[],
    systemStateSchedule: {
      academicYearId: 0,
      firstRoundStartAt: null,
      firstRoundEndAt: null,
      teacherReviewEndAt: null,
      secondRoundEndAt: null,
      autoEnabled: false,
      updatedAt: new Date().toISOString(),
    } as SystemStateSchedule,
    stateHistory: [] as StateHistory[],
    autoAssignmentLogs: [] as AutoAssignmentLog[],
    importTasks: [] as ImportTask[],
    importLogs: [] as ImportLog[],
    students: [] as StudentWithStatus[],
    teachers: [] as TeacherWithStatus[],
    admins: [] as AdminInfo[],
    applications: [] as Application[],
    admissions: [] as Admission[],
    announcements: [] as Announcement[],
    logs: [] as LogEntry[],
  }
}

export const useSharedStore = defineStore('shared', () => {
  /* 启动即清理旧版遗留缓存 */
  removeLegacyStorage()

  const defaults = createDefaultState()

  /* 系统状态 */
  const systemState = ref<SystemState>(defaults.systemState)

  /* 当前 ACTIVE 学年 ID */
  const currentAcademicYearId = ref<number>(defaults.currentAcademicYearId)

  /* 学年列表 */
  const academicYears = ref<AcademicYear[]>(defaults.academicYears)

  /* 系统状态切换配置 */
  const systemStateSchedule = ref<SystemStateSchedule>(defaults.systemStateSchedule)

  /* 状态变更历史（只追加） */
  const stateHistory = ref<StateHistory[]>(defaults.stateHistory)

  /* 自动分配日志 */
  const autoAssignmentLogs = ref<AutoAssignmentLog[]>(defaults.autoAssignmentLogs)

  /* 导入任务列表 */
  const importTasks = ref<ImportTask[]>(defaults.importTasks)

  /* 导入日志列表 */
  const importLogs = ref<ImportLog[]>(defaults.importLogs)

  /* 学生列表（带账号状态）— 内容取决于当前角色的服务端裁剪范围 */
  const students = ref<StudentWithStatus[]>(defaults.students)

  /* 导师列表（带账号状态） */
  const teachers = ref<TeacherWithStatus[]>(defaults.teachers)

  /* 管理员列表 */
  const admins = ref<AdminInfo[]>(defaults.admins)

  /* 申请列表 */
  const applications = ref<Application[]>(defaults.applications)

  /* 录取列表 */
  const admissions = ref<Admission[]>(defaults.admissions)

  /* 公告列表 */
  const announcements = ref<Announcement[]>(defaults.announcements)

  /* 日志列表 */
  const logs = ref<LogEntry[]>(defaults.logs)

  /* 标记数据是否已从后端加载过（按角色，切换账号后重置） */
  const isLoaded = ref(false)

  /* 当前内存中数据所属的角色 — 用于检测账号/角色切换 */
  const loadedRole = ref<UserRole | null>(null)

  /**
   * 清空内存中的角色数据。
   *
   * 用于登出、登录、切换账号/角色：绝不能让上一个账号的数据留到下一位用户。
   * 不触碰 sessionStorage 中的 JWT（那由 auth store 负责）。
   */
  function clear() {
    const d = createDefaultState()
    systemState.value = d.systemState
    currentAcademicYearId.value = d.currentAcademicYearId
    academicYears.value = d.academicYears
    systemStateSchedule.value = d.systemStateSchedule
    stateHistory.value = d.stateHistory
    autoAssignmentLogs.value = d.autoAssignmentLogs
    importTasks.value = d.importTasks
    importLogs.value = d.importLogs
    students.value = d.students
    teachers.value = d.teachers
    admins.value = d.admins
    applications.value = d.applications
    admissions.value = d.admissions
    announcements.value = d.announcements
    logs.value = d.logs
    isLoaded.value = false
    loadedRole.value = null
    removeLegacyStorage()
  }

  /* 重置到默认状态（演示重置用）— 仅内存，不落盘 */
  function reset() {
    clear()
  }

  /**
   * 从后端加载当前角色有权访问的数据（server authority）。
   *
   * @param role 当前登录用户角色。由调用方**显式传入**（App.vue / router / 各角色 store），
   *             本 store 不 import auth store —— 那会形成模块级循环依赖，
   *             并可能在 store 初始化前求值。未传时回退到本标签页已加载的角色
   *             （首次加载且未传时按 null 处理，即只请求角色无关的公开数据，属于安全方向）。
   */
  async function loadFromServer(role?: UserRole | null): Promise<void> {
    const effectiveRole = role ?? loadedRole.value

    /* 角色/账号切换 — 显式传入的角色与内存中数据所属角色不同，先丢弃上一个角色的数据 */
    if (role !== undefined && loadedRole.value !== null && loadedRole.value !== role) {
      clear()
    }

    const data = await loadAllFromServer({
      role: effectiveRole,
      currentAcademicYearId: currentAcademicYearId.value || null,
    })

    systemState.value = data.systemState
    if (data.currentAcademicYearId !== null) {
      currentAcademicYearId.value = data.currentAcademicYearId
    }
    academicYears.value = data.academicYears
    if (data.systemStateSchedule) {
      systemStateSchedule.value = data.systemStateSchedule
    }
    stateHistory.value = data.stateHistory
    students.value = data.students.map((s) => ({
      ...s,
      status: AccountStatus.ACTIVE,
    })) as StudentWithStatus[]
    teachers.value = data.teachers.map((t) => ({
      ...t,
      status: AccountStatus.ACTIVE,
    })) as TeacherWithStatus[]
    admins.value = data.admins
    applications.value = data.applications
    admissions.value = data.admissions
    announcements.value = data.announcements
    autoAssignmentLogs.value = data.autoAssignmentLogs
    importTasks.value = data.importTasks
    importLogs.value = data.importLogs
    logs.value = data.logs

    loadedRole.value = effectiveRole
    isLoaded.value = true
  }

  return {
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
    isLoaded,
    loadedRole,
    clear,
    reset,
    loadFromServer,
  }
})
