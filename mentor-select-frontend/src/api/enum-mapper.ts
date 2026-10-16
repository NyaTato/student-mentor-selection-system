/**
 * 前后端枚举映射
 *
 * 后端使用整数枚举（models.IntegerChoices）
 * 前端使用字符串枚举（src/types/index.ts）
 *
 * 本模块提供双向转换，确保 API 层与 UI 层解耦。
 */
import {
  SystemState,
  StateTransitionType,
  AcademicYearStatus,
  ImportTaskStatus,
  ImportRowStatus,
  AutoAssignmentStatus,
  UserRole,
  ApplicationStatus,
  AssignmentSource,
} from '@/types'

/* ========== 后端整数 → 前端字符串 ========== */

export const systemStateFromBackend: Record<number, SystemState> = {
  0: SystemState.INIT,
  1: SystemState.FIRST_ROUND_OPEN,
  2: SystemState.TEACHER_REVIEW,
  3: SystemState.SECOND_ROUND_OPEN,
  4: SystemState.AUTO_ASSIGN,
  5: SystemState.FINISHED,
}

export const stateTransitionTypeFromBackend: Record<number, StateTransitionType> = {
  1: StateTransitionType.MANUAL_FORWARD,
  2: StateTransitionType.MANUAL_ROLLBACK,
  3: StateTransitionType.AUTO_SCHEDULED,
}

/* 后端 AcademicYearStatus: 0=INACTIVE, 1=ACTIVE, 2=ARCHIVED
 * 前端 AcademicYearStatus: DRAFT, ACTIVE, CLOSED
 * 映射：INACTIVE→DRAFT, ACTIVE→ACTIVE, ARCHIVED→CLOSED */
export const academicYearStatusFromBackend: Record<number, AcademicYearStatus> = {
  0: AcademicYearStatus.DRAFT,
  1: AcademicYearStatus.ACTIVE,
  2: AcademicYearStatus.CLOSED,
}

/* 后端 ImportTaskStatus: 0=PENDING, 1=PROCESSING, 2=SUCCESS, 3=PARTIAL, 4=FAILED
 * 前端 ImportTaskStatus: PENDING, PROCESSING, COMPLETED, PARTIALLY_COMPLETED, FAILED
 * 映射：PENDING→PENDING, PROCESSING→PROCESSING, SUCCESS→COMPLETED, PARTIAL→PARTIALLY_COMPLETED, FAILED→FAILED */
export const importTaskStatusFromBackend: Record<number, ImportTaskStatus> = {
  0: ImportTaskStatus.PENDING,
  1: ImportTaskStatus.PROCESSING,
  2: ImportTaskStatus.COMPLETED,
  3: ImportTaskStatus.PARTIALLY_COMPLETED,
  4: ImportTaskStatus.FAILED,
}

export const importRowStatusFromBackend: Record<number, ImportRowStatus> = {
  1: ImportRowStatus.SUCCESS,
  2: ImportRowStatus.FAILED,
}

/* 后端 AutoAssignmentStatus: 0=RUNNING, 1=SUCCESS, 2=PARTIAL, 3=FAILED, 4=REVOKED
 * 前端 AutoAssignmentStatus: PENDING, RUNNING, COMPLETED, PARTIALLY_COMPLETED, REVOKED
 * 映射：RUNNING→RUNNING, SUCCESS→COMPLETED, PARTIAL→PARTIALLY_COMPLETED, FAILED→FAILED, REVOKED→REVOKED
 * 注意：前端 PENDING 用于尚未执行的状态，后端无对应值 */
export const autoAssignmentStatusFromBackend: Record<number, AutoAssignmentStatus> = {
  0: AutoAssignmentStatus.RUNNING,
  1: AutoAssignmentStatus.COMPLETED,
  2: AutoAssignmentStatus.PARTIALLY_COMPLETED,
  3: AutoAssignmentStatus.FAILED,
  4: AutoAssignmentStatus.REVOKED,
}

/* 后端 UserRole: 1=STUDENT, 2=TEACHER, 3=ADMIN */
export const userRoleFromBackend: Record<number, UserRole> = {
  1: UserRole.STUDENT,
  2: UserRole.TEACHER,
  3: UserRole.ADMIN,
}

/* 后端 ApplicationStatus: 1=PENDING, 2=APPROVED, 3=REJECTED
 * 前端 ApplicationStatus: PENDING, ACCEPTED, REJECTED, CANCELLED
 * 映射：PENDING→PENDING, APPROVED→ACCEPTED, REJECTED→REJECTED
 * 前端 CANCELLED 无后端对应值（业务上申请不可删除） */
export const applicationStatusFromBackend: Record<number, ApplicationStatus> = {
  1: ApplicationStatus.PENDING,
  2: ApplicationStatus.ACCEPTED,
  3: ApplicationStatus.REJECTED,
}

/* 后端 AdmissionSource: 1=ADMIT_ROUND1, 2=ADMIT_ROUND2, 3=MANUAL, 4=AUTO_ASSIGNED
 * 前端 AssignmentSource: ROUND1="第一轮录取", ROUND2="第二轮匹配", MANUAL="管理员人工分配", AUTO_ASSIGNED="系统自动分配" */
export const assignmentSourceFromBackend: Record<number, AssignmentSource> = {
  1: AssignmentSource.ROUND1,
  2: AssignmentSource.ROUND2,
  3: AssignmentSource.MANUAL,
  4: AssignmentSource.AUTO_ASSIGNED,
}

/* ========== 前端字符串 → 后端整数 ========== */

export const userRoleToBackend: Record<UserRole, number> = {
  [UserRole.STUDENT]: 1,
  [UserRole.TEACHER]: 2,
  [UserRole.ADMIN]: 3,
}

export const applicationRoundToBackend = {
  1: 1,
  2: 2,
} as const

/* ========== 类型转换辅助函数 ========== */

export function mapSystemState(value: number | null | undefined): SystemState | null {
  if (value === null || value === undefined) return null
  return systemStateFromBackend[value] ?? SystemState.INIT
}

export function mapAcademicYearStatus(value: number): AcademicYearStatus {
  return academicYearStatusFromBackend[value] ?? AcademicYearStatus.DRAFT
}

export function mapApplicationStatus(value: number): ApplicationStatus {
  return applicationStatusFromBackend[value] ?? ApplicationStatus.PENDING
}

export function mapAssignmentSource(value: number): AssignmentSource {
  return assignmentSourceFromBackend[value] ?? AssignmentSource.MANUAL
}

export function mapAutoAssignmentStatus(value: number): AutoAssignmentStatus {
  return autoAssignmentStatusFromBackend[value] ?? AutoAssignmentStatus.PENDING
}

export function mapImportTaskStatus(value: number): ImportTaskStatus {
  return importTaskStatusFromBackend[value] ?? ImportTaskStatus.PENDING
}

export function mapStateTransitionType(value: number): StateTransitionType {
  return stateTransitionTypeFromBackend[value] ?? StateTransitionType.MANUAL_FORWARD
}

export function mapUserRole(value: number): UserRole {
  return userRoleFromBackend[value] ?? UserRole.STUDENT
}
