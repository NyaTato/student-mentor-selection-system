import {
  ApplicationStatus,
  AssignmentSource,
  ImportTaskStatus,
  ImportRowStatus,
  AutoAssignmentStatus,
  StateTransitionType,
  UserRole,
} from '@/types'

export type BadgeVariant = 'default' | 'success' | 'warning' | 'error'
export interface BadgeConfig {
  variant: BadgeVariant
  label: string
}

/* 申请状态 → 徽章配置 */
export function getApplicationStatusBadge(status: ApplicationStatus): BadgeConfig {
  switch (status) {
    case ApplicationStatus.PENDING:
      return { variant: 'warning', label: '待审核' }
    case ApplicationStatus.ACCEPTED:
      return { variant: 'success', label: '已录取' }
    case ApplicationStatus.REJECTED:
      return { variant: 'error', label: '已拒绝' }
    case ApplicationStatus.CANCELLED:
      return { variant: 'default', label: '已取消' }
    default:
      return { variant: 'default', label: '未知' }
  }
}

/* 分配来源 → 徽章配置 */
export function getAssignmentSourceBadge(source: AssignmentSource): BadgeConfig {
  switch (source) {
    case AssignmentSource.ROUND1:
      return { variant: 'success', label: '第一轮录取' }
    case AssignmentSource.ROUND2:
      return { variant: 'warning', label: '第二轮匹配' }
    case AssignmentSource.MANUAL:
      return { variant: 'default', label: '管理员分配' }
    case AssignmentSource.AUTO_ASSIGNED:
      return { variant: 'success', label: '系统自动分配' }
    default:
      return { variant: 'default', label: '未知' }
  }
}

/* 导入任务状态 → 徽章配置 */
export function getImportTaskStatusBadge(status: ImportTaskStatus): BadgeConfig {
  switch (status) {
    case ImportTaskStatus.PENDING:
      return { variant: 'default', label: '等待中' }
    case ImportTaskStatus.PROCESSING:
      return { variant: 'warning', label: '处理中' }
    case ImportTaskStatus.COMPLETED:
      return { variant: 'success', label: '完成' }
    case ImportTaskStatus.PARTIALLY_COMPLETED:
      return { variant: 'warning', label: '部分完成' }
    case ImportTaskStatus.FAILED:
      return { variant: 'error', label: '失败' }
    default:
      return { variant: 'default', label: '未知' }
  }
}

/* 自动分配状态 → 徽章配置 */
export function getAutoAssignmentStatusBadge(status: AutoAssignmentStatus): BadgeConfig {
  switch (status) {
    case AutoAssignmentStatus.COMPLETED:
      return { variant: 'success', label: '完成' }
    case AutoAssignmentStatus.PARTIALLY_COMPLETED:
      return { variant: 'warning', label: '部分完成' }
    case AutoAssignmentStatus.RUNNING:
      return { variant: 'default', label: '运行中' }
    case AutoAssignmentStatus.REVOKED:
      return { variant: 'error', label: '已撤销' }
    case AutoAssignmentStatus.PENDING:
      return { variant: 'default', label: '等待中' }
    default:
      return { variant: 'default', label: '—' }
  }
}

/* 状态转换类型 → 徽章配置 */
export function getStateTransitionTypeBadge(type: StateTransitionType): BadgeConfig {
  switch (type) {
    case StateTransitionType.MANUAL_FORWARD:
      return { variant: 'default', label: '手动推进' }
    case StateTransitionType.MANUAL_ROLLBACK:
      return { variant: 'error', label: '手动回退' }
    case StateTransitionType.AUTO_SCHEDULED:
      return { variant: 'success', label: '自动触发' }
    default:
      return { variant: 'default', label: '未知' }
  }
}

/* 用户角色 → 中文标签 */
export function getRoleLabel(role: UserRole): string {
  switch (role) {
    case UserRole.STUDENT:
      return '学生'
    case UserRole.TEACHER:
      return '导师'
    case UserRole.ADMIN:
      return '管理员'
    default:
      return '未知'
  }
}

/* 导入行状态 → 徽章配置 */
export function getImportRowStatusBadge(status: ImportRowStatus): BadgeConfig {
  return status === ImportRowStatus.SUCCESS
    ? { variant: 'success', label: '成功' }
    : { variant: 'error', label: '失败' }
}
