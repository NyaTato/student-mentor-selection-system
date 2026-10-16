/* 系统状态枚举 — 对应 PROJECT.md 4.1（6 状态，含 AUTO_ASSIGN） */
export enum SystemState {
  INIT = 'INIT',
  FIRST_ROUND_OPEN = 'FIRST_ROUND_OPEN',
  TEACHER_REVIEW = 'TEACHER_REVIEW',
  SECOND_ROUND_OPEN = 'SECOND_ROUND_OPEN',
  AUTO_ASSIGN = 'AUTO_ASSIGN',
  FINISHED = 'FINISHED',
}

/* 状态转换类型 — 对应 PROJECT.md 4.3 */
export enum StateTransitionType {
  MANUAL_FORWARD = 'MANUAL_FORWARD',
  MANUAL_ROLLBACK = 'MANUAL_ROLLBACK',
  AUTO_SCHEDULED = 'AUTO_SCHEDULED',
}

/* 学年状态 — 对应 PROJECT.md 13.1 / DATABASE.md AcademicYearStatus */
export enum AcademicYearStatus {
  DRAFT = 'DRAFT',
  ACTIVE = 'ACTIVE',
  CLOSED = 'CLOSED',
}

/* 导入任务状态 — 对应 DATABASE.md ImportTaskStatus */
export enum ImportTaskStatus {
  PENDING = 'PENDING',
  PROCESSING = 'PROCESSING',
  COMPLETED = 'COMPLETED',
  PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED',
  FAILED = 'FAILED',
}

/* 导入行状态 — 对应 DATABASE.md ImportRowStatus */
export enum ImportRowStatus {
  SUCCESS = 'SUCCESS',
  FAILED = 'FAILED',
}

/* 自动分配批次状态 — 对应 DATABASE.md AutoAssignmentStatus */
export enum AutoAssignmentStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  COMPLETED = 'COMPLETED',
  PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED',
  FAILED = 'FAILED',
  REVOKED = 'REVOKED',
}

/* 用户角色 */
export enum UserRole {
  STUDENT = 'STUDENT',
  TEACHER = 'TEACHER',
  ADMIN = 'ADMIN',
}

/* 申请状态 */
export enum ApplicationStatus {
  PENDING = 'PENDING',
  ACCEPTED = 'ACCEPTED',
  REJECTED = 'REJECTED',
  CANCELLED = 'CANCELLED',
}

/* 学生个人状态 — 对应 PROJECT.md 5.2 Dashboard */
export enum StudentStatus {
  NOT_SUBMITTED = 'NOT_SUBMITTED',
  WAITING_REVIEW = 'WAITING_REVIEW',
  ACCEPTED = 'ACCEPTED',
  REJECTED = 'REJECTED',
  ROUND2_MATCHED = 'ROUND2_MATCHED',
  WAITING_ASSIGNMENT = 'WAITING_ASSIGNMENT',
}

/* 分配来源 — 对应 PROJECT.md R4-03（4 来源，含系统自动分配） */
export enum AssignmentSource {
  ROUND1 = '第一轮录取',
  ROUND2 = '第二轮匹配',
  MANUAL = '管理员人工分配',
  AUTO_ASSIGNED = '系统自动分配',
}

/* 用户信息 */
export interface UserInfo {
  id: number
  username: string
  name: string
  role: UserRole
}

/* 学生信息 */
export interface StudentInfo extends UserInfo {
  studentId: string
  major: string
  grade: string
  department: string
  phone: string
  /* v2 学生档案主键（student_id），用于 v2 接口路径参数；id 字段仍为 user_id */
  studentPk?: number
}

/* 导师信息 */
export interface TeacherInfo extends UserInfo {
  teacherNumber: string
  department: string
  title: string
  researchArea: string
  profile: string
  maxQuota: number
  currentAdmitted: number
  projectDirection: string
  researchTopics: string
  requirements: string
  /* v2 导师档案主键（teacher_id），用于 v2 接口路径参数；id 字段仍为 user_id */
  teacherPk?: number
}

/* 申请记录 — R9-09：业务数据通过 academic_year_id 隔离 */
export interface Application {
  id: number
  academicYearId: number
  studentId: number
  teacherId: number
  round: 1 | 2
  status: ApplicationStatus
  createdAt: string
  updatedAt: string
}

/* 录取记录 — 对应 DATABASE.md admission（含学年与自动分配批次） */
export interface Admission {
  id: number
  academicYearId: number
  studentId: number
  teacherId: number
  source: AssignmentSource
  applicationId: number | null
  autoAssignmentLogId: number | null
  createdAt: string
}

/* 系统公告 — R9-09：业务数据通过 academic_year_id 隔离 */
export interface Announcement {
  id: number
  academicYearId: number
  title: string
  content: string
  published: boolean
  createdAt: string
  updatedAt: string
}

/* 历史记录条目 */
export interface HistoryEntry {
  id: number
  round: string
  teacherName: string
  status: string
  action: string
  timestamp: string
}

/* 管理员信息 */
export interface AdminInfo {
  id: number
  username: string
  name: string
  role: UserRole
  createdAt: string
  lastLoginAt?: string
  /* v2 管理员档案主键（admin_id），用于 v2 接口路径参数；id 字段仍为 user_id */
  adminPk?: number
}

/* 日志类型 */
export enum LogType {
  LOGIN = 'LOGIN',
  OPERATION = 'OPERATION',
  ERROR = 'ERROR',
}

/* 日志条目 — 对应 PROJECT.md 12.2 */
export interface LogEntry {
  id: number
  type: LogType
  operator: string
  action: string
  target?: string
  ip: string
  timestamp: string
  detail?: string
}

/* 账号状态 */
export enum AccountStatus {
  ACTIVE = 'ACTIVE',
  DISABLED = 'DISABLED',
}

/* ============ 学年与状态实体（PROJECT.md 13 / DATABASE.md） ============ */

/* 学年 — 对应 DATABASE.md academic_year */
export interface AcademicYear {
  id: number
  name: string
  startYear: number
  endYear: number
  status: AcademicYearStatus
  activatedAt: string | null
  closedAt: string | null
  createdAt: string
  updatedAt: string
}

/* 系统状态切换配置 — 对应 DATABASE.md system_state_schedule */
export interface SystemStateSchedule {
  academicYearId: number
  firstRoundStartAt: string | null
  firstRoundEndAt: string | null
  teacherReviewEndAt: string | null
  secondRoundEndAt: string | null
  autoEnabled: boolean
  updatedAt: string
}

/* 状态变更历史 — 对应 DATABASE.md state_history（只追加） */
export interface StateHistory {
  id: number
  academicYearId: number
  fromState: SystemState
  toState: SystemState
  transitionType: StateTransitionType
  reason: string | null
  operatorId: number
  operatorName: string
  createdAt: string
}

/* ============ 自动分配（PROJECT.md 3.5 / DATABASE.md） ============ */

/* 自动分配批次日志 — 对应 DATABASE.md auto_assignment_log */
export interface AutoAssignmentLog {
  id: number
  academicYearId: number
  status: AutoAssignmentStatus
  totalCandidates: number
  assignedCount: number
  failedCount: number
  isRevoked: boolean
  revokedAt: string | null
  operatorId: number
  operatorName: string
  createdAt: string
  completedAt: string | null
}

/* ============ Excel 导入（PROJECT.md 7.13 / DATABASE.md） ============ */

/* 导入任务 — 对应 DATABASE.md import_task */
export interface ImportTask {
  id: number
  academicYearId: number
  role: UserRole
  fileName: string
  fileSize: number
  status: ImportTaskStatus
  totalRows: number
  successCount: number
  failureCount: number
  operatorId: number
  operatorName: string
  createdAt: string
  completedAt: string | null
}

/* 导入日志 — 对应 DATABASE.md import_log（每行一条） */
export interface ImportLog {
  id: number
  taskId: number
  rowNumber: number
  rowData: string
  status: ImportRowStatus
  failReason: string | null
  createdAt: string
}

/* ============ 导师名额（PROJECT.md R9-08 / DATABASE.md teacher_quota） ============ */

/* 导师名额 — 按学年独立设置 */
export interface TeacherQuota {
  id: number
  academicYearId: number
  teacherId: number
  maxQuota: number
  createdAt: string
  updatedAt: string
}
