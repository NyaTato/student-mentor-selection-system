/**
 * 数据加载器 — 从后端拉取业务数据并转换为前端格式
 *
 * 模块路由策略（Frontend Integration）：
 *   - v2（/api/v2/，requestV2）：
 *     users/students/teachers/admins 档案，
 *     以及已迁移的业务模块
 *     applications / assignments / announcements / system /
 *     academic-years / teachers(profiles, quotas) / statistics
 *   - v1（/api/v1/，request）：**尚未迁移**的模块
 *     imports（导入任务/日志）、logs（操作日志/登录日志）
 *   - auth（登录/登出/刷新/me）：保留 v1（后端未提供 v2 等价接口）
 *
 * 角色范围（server authority）：
 *   后端在 queryset 层做角色裁剪，前端只请求当前角色**有权访问**的数据：
 *   - 管理员：全部
 *   - 导师：自己的导师档案、与自己有申请/录取关系的学生、自己的申请与录取
 *   - 学生：自己的学生档案、自己的申请与录取
 *   未被授权的端点**根本不发起请求**（而不是请求后被静默 catch 成空数据，
 *   那会让越权失败变得不可见）。容忍范围仅限「资源尚不存在」的 404；
 *   403 一律上抛。
 *
 * 名额展示（server authority）：
 *   导师剩余名额只能来自后端**汇总接口** `teachers/profiles/directory/`
 *   （admitted_count / remaining_quota）。角色裁剪后的录取列表对导师/学生而言
 *   不是全量，用它自行 count 会得出错误（偏大）的剩余名额。
 *
 * 分页：
 *   getList / getListV2 会自动翻完所有页（有界循环 + total/page_size 约束），
 *   不再只取第一页（此前的「前 100 条截断」是错的）。
 */
import { request, requestV2, errorStatus, type PaginatedData } from './http'
import {
  mapSystemState,
  mapAcademicYearStatus,
  mapApplicationStatus,
  mapAssignmentSource,
  mapAutoAssignmentStatus,
  mapImportTaskStatus,
  mapStateTransitionType,
  mapUserRole,
  importRowStatusFromBackend,
} from './enum-mapper'
import {
  SystemState,
  AcademicYearStatus,
  ImportRowStatus,
  UserRole,
  type StudentInfo,
  type TeacherInfo,
  type AdminInfo,
  type Announcement,
  type Application,
  type Admission,
  type AcademicYear,
  type SystemStateSchedule,
  type StateHistory,
  type AutoAssignmentLog,
  type ImportTask,
  type ImportLog,
  type LogEntry,
  LogType,
} from '@/types'

/* ========== 分页参数 ========== */

/* 后端 max_page_size = 100；分页循环上限用于防止后端 total 异常时死循环 */
const PAGE_SIZE = 100
const MAX_PAGES = 50

/* ========== 后端 DTO 类型定义 ========== */

interface BackendAcademicYear {
  id: number
  name: string
  start_year: number
  end_year: number
  status: number
  activated_at: string | null
  closed_at: string | null
  created_at: string
  updated_at: string
}

interface BackendStudentProfile {
  /* v2 字段（canonical：id === user_id） */
  id: number          /* v2 student_id（== user_id） */
  user_id: number
  student_number: string
  name: string
  major: string
  class_name: string
  department: string | null
  phone: string
  created_at: string
  updated_at: string
}

interface BackendTeacherProfile {
  /* v2 字段（canonical：id === user_id） */
  id: number          /* v2 teacher_id（== user_id） */
  user_id: number
  teacher_number: string
  name: string
  college: string
  title: string
  research_area: string
  profile: string | null
  graduation_direction: string | null
  thesis_topic: string | null
  student_requirement: string | null
  created_at: string
  updated_at: string
}

/* v2 导师目录汇总 — GET /api/v2/teachers/profiles/directory/?academic_year=<id>
 * 只含汇总名额，不含任何学生明细；未配置名额时 has_quota=false / remaining_quota=0 */
interface BackendTeacherDirectory {
  teacher_id: number          /* == canonical user_id */
  teacher_number: string
  name: string
  college: string
  title: string
  research_area: string
  has_quota: boolean
  max_quota: number | null
  admitted_count: number
  remaining_quota: number
}

interface BackendTeacherQuota {
  id: number
  academic_year: number
  teacher: number
  teacher_name: string
  teacher_number: string
  max_quota: number
}

interface BackendAnnouncement {
  id: number
  academic_year: number
  title: string
  content: string
  is_published: boolean
  published_at: string | null
  created_by: number
  created_at: string
  updated_at: string
}

interface BackendApplication {
  id: number
  academic_year: number
  student: number
  student_name: string
  student_number: string
  teacher: number
  teacher_name: string
  teacher_number: string
  round: number
  round_display: string
  status: number
  status_display: string
  created_at: string
  updated_at: string
}

interface BackendAdmission {
  id: number
  academic_year: number
  student: number
  student_name: string
  student_number: string
  teacher: number
  teacher_name: string
  teacher_number: string
  source: number
  source_display: string
  application: number | null
  auto_assignment_log: number | null
  created_at: string
}

interface BackendSystemState {
  id: number
  academic_year: number
  current_state: number
  previous_state: number | null
  state_changed_at: string
}

interface BackendSystemStateSchedule {
  id: number
  academic_year: number
  first_round_start_at: string | null
  first_round_end_at: string | null
  teacher_review_end_at: string | null
  second_round_end_at: string | null
  auto_enabled: boolean
  updated_at: string
}

interface BackendStateHistory {
  id: number
  academic_year: number
  from_state: number
  to_state: number
  transition_type: number
  reason: string | null
  operator: number | null
  operator_name: string | null
  created_at: string
}

interface BackendAutoAssignmentLog {
  id: number
  academic_year: number
  status: number
  total_unassigned: number
  assigned_count: number
  failed_count: number
  triggered_by: number | null
  triggered_by_name: string | null
  started_at: string | null
  finished_at: string | null
  is_revoked: boolean
  revoked_at: string | null
  revoked_by: number | null
  revoked_by_name: string | null
  created_at: string
}

interface BackendImportTask {
  id: number
  academic_year: number
  role: number
  role_display: string
  status: number
  status_display: string
  file_name: string
  file_size: number
  total_rows: number
  success_count: number
  failed_count: number
  started_at: string | null
  finished_at: string | null
  triggered_by: number | null
  triggered_by_name: string | null
  created_at: string
}

interface BackendImportLog {
  id: number
  task: number
  row_number: number
  row_data: string
  status: number
  error_reason: string | null
  created_at: string
}

interface BackendOperationLog {
  id: number
  academic_year: number | null
  user: number | null
  action: number
  action_display: string
  target_type: string | null
  target_id: number | null
  detail: string | null
  ip_address: string | null
  created_at: string
}

interface BackendLoginLog {
  id: number
  user: number | null
  username: string
  ip_address: string | null
  user_agent: string | null
  is_success: boolean
  fail_reason: string | null
  created_at: string
}

/* v2 管理员档案 — 对应 GET /api/v2/admins/list 返回的 list 元素 */
interface BackendAdminProfile {
  id: number          /* v2 admin_id（== user_id） */
  user_id: number
  username: string    /* 登录用户名（来自关联 User） */
  name: string
  created_at: string
  updated_at: string
}

/* ========== DTO 转换函数 ========== */

function toAcademicYear(b: BackendAcademicYear): AcademicYear {
  return {
    id: b.id,
    name: b.name,
    startYear: b.start_year,
    endYear: b.end_year,
    status: mapAcademicYearStatus(b.status),
    activatedAt: b.activated_at,
    closedAt: b.closed_at,
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  }
}

function toStudentInfo(b: BackendStudentProfile): StudentInfo {
  return {
    id: b.user_id,                  /* id 字段保留 user_id（前端兼容） */
    studentPk: b.id,                /* v2 student_id（canonical 下与 user_id 相同） */
    username: b.student_number,     /* v2 不返回 username，用学号兜底 */
    name: b.name,
    role: UserRole.STUDENT,
    studentId: b.student_number,
    major: b.major,
    grade: b.class_name,
    department: b.department ?? '',
    phone: b.phone ?? '',
  }
}

/**
 * 导师档案 → 前端格式
 *
 * 名额只取自后端汇总目录（directory）：
 * 对导师/学生而言录取列表是**角色裁剪后**的子集，用它自行统计已录取数
 * 会得到偏大的剩余名额；只有后端 admitted_count 才是权威值。
 */
function toTeacherInfo(
  b: BackendTeacherProfile,
  directory: Map<number, BackendTeacherDirectory>,
): TeacherInfo {
  const agg = directory.get(b.user_id)
  return {
    id: b.user_id,                  /* id 字段保留 user_id（前端兼容） */
    teacherPk: b.id,                /* v2 teacher_id（canonical 下与 user_id 相同） */
    username: b.teacher_number,     /* v2 不返回 username，用工号兜底 */
    name: b.name,
    role: UserRole.TEACHER,
    teacherNumber: b.teacher_number,
    department: b.college,
    title: b.title,
    researchArea: b.research_area,
    profile: b.profile ?? '',
    /* 未配置名额 → maxQuota=0（视为已关闭，而不是「无限」） */
    maxQuota: agg?.max_quota ?? 0,
    currentAdmitted: agg?.admitted_count ?? 0,
    projectDirection: b.graduation_direction ?? '',
    researchTopics: b.thesis_topic ?? '',
    requirements: b.student_requirement ?? '',
  }
}

function toAdminInfo(b: BackendAdminProfile): AdminInfo {
  return {
    id: b.user_id,                  /* id 字段保留 user_id（前端兼容） */
    adminPk: b.id,                  /* v2 admin_id（canonical 下与 user_id 相同） */
    username: b.username ?? b.name, /* 优先使用真实 username，老数据用 name 兜底 */
    name: b.name,
    role: UserRole.ADMIN,
    createdAt: b.created_at,
  }
}

function toAnnouncement(b: BackendAnnouncement): Announcement {
  return {
    id: b.id,
    academicYearId: b.academic_year,
    title: b.title,
    content: b.content,
    published: b.is_published,
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  }
}

function toApplication(b: BackendApplication): Application {
  return {
    id: b.id,
    academicYearId: b.academic_year,
    studentId: b.student,
    teacherId: b.teacher,
    round: b.round as 1 | 2,
    status: mapApplicationStatus(b.status),
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  }
}

function toAdmission(b: BackendAdmission): Admission {
  return {
    id: b.id,
    academicYearId: b.academic_year,
    studentId: b.student,
    teacherId: b.teacher,
    source: mapAssignmentSource(b.source),
    applicationId: b.application,
    autoAssignmentLogId: b.auto_assignment_log,
    createdAt: b.created_at,
  }
}

function toSystemStateSchedule(b: BackendSystemStateSchedule): SystemStateSchedule {
  return {
    academicYearId: b.academic_year,
    firstRoundStartAt: b.first_round_start_at,
    firstRoundEndAt: b.first_round_end_at,
    teacherReviewEndAt: b.teacher_review_end_at,
    secondRoundEndAt: b.second_round_end_at,
    autoEnabled: b.auto_enabled,
    updatedAt: b.updated_at,
  }
}

function toStateHistory(b: BackendStateHistory): StateHistory {
  const fromState = mapSystemState(b.from_state) ?? SystemState.INIT
  const toState = mapSystemState(b.to_state) ?? SystemState.INIT
  return {
    id: b.id,
    academicYearId: b.academic_year,
    fromState,
    toState,
    transitionType: mapStateTransitionType(b.transition_type),
    reason: b.reason,
    operatorId: b.operator ?? 0,
    operatorName: b.operator_name ?? '未知',
    createdAt: b.created_at,
  }
}

function toAutoAssignmentLog(b: BackendAutoAssignmentLog): AutoAssignmentLog {
  return {
    id: b.id,
    academicYearId: b.academic_year,
    status: mapAutoAssignmentStatus(b.status),
    totalCandidates: b.total_unassigned,
    assignedCount: b.assigned_count,
    failedCount: b.failed_count,
    isRevoked: b.is_revoked,
    revokedAt: b.revoked_at,
    operatorId: b.triggered_by ?? 0,
    operatorName: b.triggered_by_name ?? '未知',
    createdAt: b.created_at,
    completedAt: b.finished_at,
  }
}

function toImportTask(b: BackendImportTask): ImportTask {
  return {
    id: b.id,
    academicYearId: b.academic_year,
    role: mapUserRole(b.role),
    fileName: b.file_name,
    fileSize: b.file_size,
    status: mapImportTaskStatus(b.status),
    totalRows: b.total_rows,
    successCount: b.success_count,
    failureCount: b.failed_count,
    operatorId: b.triggered_by ?? 0,
    operatorName: b.triggered_by_name ?? '未知',
    createdAt: b.created_at,
    completedAt: b.finished_at,
  }
}

function toImportLog(b: BackendImportLog): ImportLog {
  return {
    id: b.id,
    taskId: b.task,
    rowNumber: b.row_number,
    rowData: b.row_data,
    status: importRowStatusFromBackend[b.status] ?? ImportRowStatus.FAILED,
    failReason: b.error_reason,
    createdAt: b.created_at,
  }
}

function toLogEntry(b: BackendOperationLog | BackendLoginLog): LogEntry {
  if ('action' in b) {
    /* OperationLog */
    return {
      id: b.id,
      type: LogType.OPERATION,
      operator: String(b.user ?? 'system'),
      action: b.action_display,
      target: b.target_type ?? undefined,
      ip: b.ip_address ?? '',
      timestamp: b.created_at,
      detail: b.detail ?? undefined,
    }
  }
  /* LoginLog */
  return {
    id: b.id,
    type: LogType.LOGIN,
    operator: b.username,
    action: b.is_success ? '登录成功' : `登录失败：${b.fail_reason ?? ''}`,
    timestamp: b.created_at,
    ip: b.ip_address ?? '',
  }
}

/* ========== 分页辅助 ========== */

/** 单页拉取函数：返回数组（非分页接口）或分页对象 */
type PageFetcher<T> = (page: number) => Promise<T[] | PaginatedData<T>>

/**
 * 翻完所有页。
 *
 * - 非分页接口（直接返回数组）：原样返回，不发第二页请求
 * - 分页接口：按 total / page_size 计算页数，逐页拉取
 *   超出 MAX_PAGES 时显式报错，避免静默截断；页码严格递增，
 *   某页为空即提前结束（后端 total 与实际不一致时不空转）
 */
async function fetchAllPages<T>(fetchPage: PageFetcher<T>): Promise<T[]> {
  const first = await fetchPage(1)
  if (Array.isArray(first)) return first

  const pageSize = first.page_size > 0 ? first.page_size : PAGE_SIZE
  const items: T[] = [...(first.list ?? [])]
  const total = typeof first.total === 'number' ? first.total : items.length
  if (items.length >= total) return items

  const totalPages = Math.ceil(total / pageSize)
  if (totalPages > MAX_PAGES) {
    throw new Error(`列表需要 ${totalPages} 页，超过安全上限 ${MAX_PAGES} 页`)
  }
  for (let page = 2; page <= totalPages; page++) {
    const data = await fetchPage(page)
    const list = Array.isArray(data) ? data : (data.list ?? [])
    if (!list.length) break
    items.push(...list)
    if (items.length >= total) break
  }
  return items
}

/* 获取列表（自动翻页）— v1 */
async function getList<T>(url: string, params?: Record<string, unknown>): Promise<T[]> {
  return fetchAllPages<T>((page) =>
    request.get<T[] | PaginatedData<T>>(url, {
      params: { ...(params ?? {}), page, page_size: PAGE_SIZE },
    }),
  )
}

/* 获取列表（自动翻页）— v2 */
async function getListV2<T>(url: string, params?: Record<string, unknown>): Promise<T[]> {
  return fetchAllPages<T>((page) =>
    requestV2.get<T[] | PaginatedData<T>>(url, {
      params: { ...(params ?? {}), page, page_size: PAGE_SIZE },
    }),
  )
}

/**
 * 容忍「资源尚不存在」（404）的可选读取。
 *
 * 只有 404 表示资源尚未创建。认证、权限、网络和服务端错误都上抛。
 */
async function optionalRead<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise
  } catch (err) {
    if (errorStatus(err) === 404) return fallback
    throw err
  }
}

/* ========== 加载全部数据 ========== */

export interface LoadedData {
  academicYears: AcademicYear[]
  currentAcademicYearId: number | null
  systemState: SystemState
  systemStateSchedule: SystemStateSchedule | null
  stateHistory: StateHistory[]
  students: StudentInfo[]
  teachers: TeacherInfo[]
  admins: AdminInfo[]
  announcements: Announcement[]
  applications: Application[]
  admissions: Admission[]
  autoAssignmentLogs: AutoAssignmentLog[]
  importTasks: ImportTask[]
  importLogs: ImportLog[]
  logs: LogEntry[]
  teacherQuotas: BackendTeacherQuota[]
}

export interface LoadOptions {
  /** 当前登录用户角色（由调用方显式传入，避免 store 之间循环依赖） */
  role: UserRole | null
  /** 当前查看的学年 ID（null / 未传则自动取 ACTIVE 学年） */
  currentAcademicYearId?: number | null
}

/**
 * 从后端加载当前角色有权访问的共享数据。
 *
 * @param options.role 当前登录用户角色（server authority 的裁剪依据）
 * @param options.currentAcademicYearId 当前查看的学年 ID
 */
export async function loadAllFromServer(options: LoadOptions): Promise<LoadedData> {
  const role = options.role
  const isAdmin = role === UserRole.ADMIN
  const isStudent = role === UserRole.STUDENT
  const isTeacher = role === UserRole.TEACHER
  /* 角色已知时才请求「按角色裁剪」的业务数据。
   * 角色为 null（会话恢复失败 / 角色字段缺失）时**不发这些请求**：
   * 后端对「角色不属于学生/导师/管理员」的调用方会走「不裁剪」分支，
   * 前端若照发请求，等于把兜底交给后端；安全方向是直接不发。 */
  const hasRole = isAdmin || isStudent || isTeacher

  /* 1. 学年列表（v2）— 所有已认证角色都需要 */
  const academicYearsRaw = await getListV2<BackendAcademicYear>('academic-years/')
  const academicYears = academicYearsRaw.map(toAcademicYear)

  /* 确定当前学年 — 若传入的学年不存在或已 CLOSED，且存在 ACTIVE 学年，则自动切换到 ACTIVE */
  let yearId = options.currentAcademicYearId ?? null
  const activeYear = academicYears.find((y) => y.status === AcademicYearStatus.ACTIVE)
  if (activeYear) {
    const requestedYear = academicYears.find((y) => y.id === yearId)
    if (!requestedYear || requestedYear.status !== AcademicYearStatus.ACTIVE) {
      yearId = activeYear.id
    }
  } else if (yearId === null) {
    yearId = academicYears[0]?.id ?? null
  }

  const yearParams = yearId ? { academic_year: yearId } : undefined

  /* 2. 导师目录（v2 公开目录 + 汇总名额）— 学生选导师 / 导师自查名额的唯一权威来源。
   *    目录接口要求 academic_year 必填，无学年时跳过（名额视为未配置）。 */
  const directoryRaw = yearId
    ? await getListV2<BackendTeacherDirectory>('teachers/profiles/directory/', yearParams)
    : []
  const directory = new Map<number, BackendTeacherDirectory>(
    directoryRaw.map((d) => [d.teacher_id, d]),
  )

  /* 3. 角色范围内的档案数据
   *    - 导师档案（公开目录）：所有已认证角色可见（用于学生选导师）
   *    - 学生档案：后端按角色裁剪（学生→自己；导师→本学年与自己有申请/录取关系的学生；
   *      管理员→全部）。导师**必须带 academic_year**，否则后端返回空集。
   *    - 管理员档案：仅管理员 */
  const [teachersRaw, studentsRaw, adminsRaw] = await Promise.all([
    getListV2<BackendTeacherProfile>('teachers/list'),
    hasRole
      ? getListV2<BackendStudentProfile>('students/list', isTeacher ? yearParams : undefined)
      : Promise.resolve([] as BackendStudentProfile[]),
    isAdmin
      ? getListV2<BackendAdminProfile>('admins/list')
      : Promise.resolve([] as BackendAdminProfile[]),
  ])

  /* 4. 申请 / 录取（v2，后端角色裁剪）— 仅角色已知时请求
   *    学生拿到的只有自己的申请与录取；导师只有与自己相关的；管理员全量。
   *    公告不按角色裁剪（非管理员只能看到已发布的），对所有登录角色可见。 */
  const [applicationsRaw, admissionsRaw, announcementsRaw] = await Promise.all([
    hasRole
      ? getListV2<BackendApplication>('applications/', yearParams)
      : Promise.resolve([] as BackendApplication[]),
    hasRole
      ? getListV2<BackendAdmission>('assignments/admissions/', yearParams)
      : Promise.resolve([] as BackendAdmission[]),
    getListV2<BackendAnnouncement>('announcements/', yearParams),
  ])

  /* 5. 名额明细（v2）— 仅管理员需要原始 quota 记录（名额管理页）；
   *    导师/学生的剩余名额一律来自上面的汇总目录。 */
  const teacherQuotas: BackendTeacherQuota[] = isAdmin
    ? yearId
      ? await getListV2<BackendTeacherQuota>(`teachers/quotas/by-year/${yearId}/`)
      : await getListV2<BackendTeacherQuota>('teachers/quotas/')
    : []

  /* 6. 系统状态、调度、历史（v2；学年可能尚未初始化 → 容忍 404） */
  let systemState = SystemState.INIT
  let systemStateSchedule: SystemStateSchedule | null = null
  let stateHistory: StateHistory[] = []
  if (yearId) {
    const stateRaw = await optionalRead(
      requestV2.get<BackendSystemState>(`system/states/by-year/${yearId}/`),
      null,
    )
    if (stateRaw) {
      systemState = mapSystemState(stateRaw.current_state) ?? SystemState.INIT
    }
    const schedules = await optionalRead(
      getListV2<BackendSystemStateSchedule>('system/schedules/', { academic_year: yearId }),
      [] as BackendSystemStateSchedule[],
    )
    if (schedules.length > 0) {
      systemStateSchedule = toSystemStateSchedule(schedules[0])
    }
    stateHistory = (
      await optionalRead(
        getListV2<BackendStateHistory>(`system/states/histories/${yearId}/`),
        [] as BackendStateHistory[],
      )
    ).map(toStateHistory)
  }

  /* 7. 自动分配日志（v2，仅管理员） */
  let autoAssignmentLogs: AutoAssignmentLog[] = []
  if (isAdmin) {
    autoAssignmentLogs = (
      await getListV2<BackendAutoAssignmentLog>('assignments/auto-logs/', yearParams)
    ).map(toAutoAssignmentLog)
  }

  /* 8. 导入任务与日志（**尚未迁移 v2**，保留 v1；仅管理员） */
  let importTasks: ImportTask[] = []
  let importLogs: ImportLog[] = []
  if (isAdmin) {
    const [tasksRaw, logsRaw] = await Promise.all([
      getList<BackendImportTask>('imports/tasks/', yearParams),
      getList<BackendImportLog>('imports/logs/', yearParams),
    ])
    importTasks = tasksRaw.map(toImportTask)
    importLogs = logsRaw.map(toImportLog)
  }

  /* 9. 操作 / 登录日志（**尚未迁移 v2**，保留 v1；仅管理员） */
  let logs: LogEntry[] = []
  if (isAdmin) {
    const [opLogs, loginLogs] = await Promise.all([
      getList<BackendOperationLog>('logs/operation/'),
      getList<BackendLoginLog>('logs/login/'),
    ])
    logs = [...opLogs.map(toLogEntry), ...loginLogs.map(toLogEntry)].sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    )
  }

  /* 转换学生/导师/管理员 */
  const students = studentsRaw.map((s) => toStudentInfo(s))
  const teachers = teachersRaw.map((t) => toTeacherInfo(t, directory))
  const admins = adminsRaw.map(toAdminInfo)

  /* 转换公告/申请/录取 */
  const announcements = announcementsRaw.map(toAnnouncement)
  const applications = applicationsRaw.map(toApplication)
  const admissions = admissionsRaw.map(toAdmission)

  return {
    academicYears,
    currentAcademicYearId: yearId,
    systemState,
    systemStateSchedule,
    stateHistory,
    students,
    teachers,
    admins,
    announcements,
    applications,
    admissions,
    autoAssignmentLogs,
    importTasks,
    importLogs,
    logs,
    teacherQuotas,
  }
}

/* ========== 单模块刷新函数（写入后用服务端数据覆盖本地状态） ========== */

/** 导师汇总目录 — v2 /teachers/profiles/directory/?academic_year=<id> */
export async function refreshTeacherDirectory(
  academicYearId: number,
): Promise<Map<number, BackendTeacherDirectory>> {
  const data = await getListV2<BackendTeacherDirectory>('teachers/profiles/directory/', {
    academic_year: academicYearId,
  })
  return new Map(data.map((d) => [d.teacher_id, d]))
}

export async function refreshApplications(academicYearId: number): Promise<Application[]> {
  const data = await getListV2<BackendApplication>('applications/', { academic_year: academicYearId })
  return data.map(toApplication)
}

export async function refreshAdmissions(academicYearId: number): Promise<Admission[]> {
  const data = await getListV2<BackendAdmission>('assignments/admissions/', {
    academic_year: academicYearId,
  })
  return data.map(toAdmission)
}

export async function refreshAnnouncements(academicYearId: number): Promise<Announcement[]> {
  const data = await getListV2<BackendAnnouncement>('announcements/', {
    academic_year: academicYearId,
  })
  return data.map(toAnnouncement)
}

/**
 * 刷新导师列表（含汇总名额）。
 *
 * 名额始终取自 v2 汇总目录，而不是「录取列表自行 count」——
 * 录取列表对非管理员是角色裁剪后的子集，自行统计会算出错误的剩余名额。
 */
export async function refreshTeachers(academicYearId?: number): Promise<TeacherInfo[]> {
  const [teachersRaw, directory] = await Promise.all([
    getListV2<BackendTeacherProfile>('teachers/list'),
    academicYearId
      ? refreshTeacherDirectory(academicYearId)
      : Promise.resolve(new Map<number, BackendTeacherDirectory>()),
  ])
  return teachersRaw.map((t) => toTeacherInfo(t, directory))
}

export async function refreshStudents(): Promise<StudentInfo[]> {
  const data = await getListV2<BackendStudentProfile>('students/list')
  return data.map((s) => toStudentInfo(s))
}

/* 刷新管理员列表 — v2 接口 GET /api/v2/admins/list */
export async function refreshAdmins(): Promise<AdminInfo[]> {
  const data = await getListV2<BackendAdminProfile>('admins/list')
  return data.map(toAdminInfo)
}

export async function refreshSystemState(academicYearId: number): Promise<{
  systemState: SystemState
  schedule: SystemStateSchedule | null
  history: StateHistory[]
}> {
  let systemState = SystemState.INIT
  let schedule: SystemStateSchedule | null = null
  let history: StateHistory[] = []
  const stateRaw = await optionalRead(
    requestV2.get<BackendSystemState>(`system/states/by-year/${academicYearId}/`),
    null,
  )
  if (stateRaw) {
    systemState = mapSystemState(stateRaw.current_state) ?? SystemState.INIT
  }
  const schedules = await optionalRead(
    getListV2<BackendSystemStateSchedule>('system/schedules/', { academic_year: academicYearId }),
    [] as BackendSystemStateSchedule[],
  )
  if (schedules.length > 0) schedule = toSystemStateSchedule(schedules[0])
  history = (
    await optionalRead(
      getListV2<BackendStateHistory>(`system/states/histories/${academicYearId}/`),
      [] as BackendStateHistory[],
    )
  ).map(toStateHistory)
  return { systemState, schedule, history }
}

export async function refreshAutoAssignmentLogs(
  academicYearId: number,
): Promise<AutoAssignmentLog[]> {
  const data = await getListV2<BackendAutoAssignmentLog>('assignments/auto-logs/', {
    academic_year: academicYearId,
  })
  return data.map(toAutoAssignmentLog)
}
