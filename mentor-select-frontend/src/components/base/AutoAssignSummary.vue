<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import type { AutoAssignmentLog } from '@/types'
import { AutoAssignmentStatus } from '@/types'
import AppCard from './AppCard.vue'
import AppButton from './AppButton.vue'
import StatusBadge from './StatusBadge.vue'
import EmptyState from './EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAutoAssignmentStatusBadge } from '@/utils/badges'

interface AssignmentRow {
  studentId: number
  studentName: string
  teacherId: number
  teacherName: string
}

const props = defineProps<{
  log: AutoAssignmentLog | null
  assignments: AssignmentRow[]
}>()

const emit = defineEmits<{
  (e: 'revoke', logId: number): void
  (e: 'export'): void
}>()

function handleRevoke() {
  if (!props.log) return
  if (!confirm('确认撤销？撤销后所有自动分配的学生将回到未匹配状态')) return
  emit('revoke', props.log.id)
}

const canRevoke = () =>
  props.log !== null &&
  !props.log.isRevoked &&
  (props.log.status === AutoAssignmentStatus.COMPLETED ||
    props.log.status === AutoAssignmentStatus.PARTIALLY_COMPLETED)
</script>

<template>
  <AppCard variant="default">
    <div v-if="log" class="summary-content">
      <!-- 顶部：状态 + 统计 -->
      <div class="summary-header">
        <div class="summary-status">
          <StatusBadge :variant="getAutoAssignmentStatusBadge(log.status).variant" :label="getAutoAssignmentStatusBadge(log.status).label" />
          <span class="summary-batch">批次 #{{ log.id }}</span>
          <span class="summary-time">{{ formatDateTime(log.createdAt) }}</span>
        </div>
        <div class="summary-stats">
          <div class="stat">
            <span class="stat-label">候选</span>
            <span class="stat-value">{{ log.totalCandidates }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">成功</span>
            <span class="stat-value stat-success">{{ log.assignedCount }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">失败</span>
            <span class="stat-value stat-fail">{{ log.failedCount }}</span>
          </div>
        </div>
      </div>

      <!-- 中部：分配结果表格 -->
      <div v-if="assignments.length" class="assignment-table">
        <div class="table-header">
          <div class="col-student">学生姓名</div>
          <div class="col-arrow"></div>
          <div class="col-teacher">导师姓名</div>
        </div>
        <div v-for="(row, idx) in assignments" :key="idx" class="table-row">
          <div class="col-student">{{ row.studentName }}</div>
          <div class="col-arrow">→</div>
          <div class="col-teacher">{{ row.teacherName }}</div>
        </div>
      </div>
      <EmptyState v-else title="暂无分配结果" description="该批次未产生分配记录" />

      <!-- 底部：操作按钮 -->
      <div class="summary-actions">
        <AppButton variant="secondary" @click="emit('export')">
          <el-icon><Download /></el-icon>
          导出结果
        </AppButton>
        <AppButton
          variant="danger"
          :disabled="!canRevoke()"
          @click="handleRevoke"
        >
          撤销整批自动分配
        </AppButton>
      </div>
    </div>

    <EmptyState v-else title="暂无自动分配记录" description="执行自动分配后，结果摘要将显示在此处" />
  </AppCard>
</template>

<style scoped>
.summary-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.summary-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.summary-batch {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
}

.summary-time {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.summary-stats {
  display: flex;
  gap: var(--spacing-md);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.stat-value {
  font-size: var(--text-headline);
  font-weight: 600;
  color: var(--color-ink);
}

.stat-success {
  color: var(--color-semantic-success);
}

.stat-fail {
  color: var(--color-semantic-error);
}

.assignment-table {
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  overflow: hidden;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 40px 1fr;
  gap: var(--spacing-sm);
  align-items: center;
  padding: var(--spacing-xs) var(--spacing-sm);
}

.table-header {
  background: var(--color-surface-2);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
}

.table-row {
  border-top: 1px solid var(--color-hairline);
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.col-arrow {
  text-align: center;
  color: var(--color-ink-subtle);
}

.summary-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
}
</style>
