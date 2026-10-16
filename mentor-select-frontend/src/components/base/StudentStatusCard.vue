<script setup lang="ts">
import { computed } from 'vue'
import { StudentStatus } from '@/types'

const props = defineProps<{
  status: StudentStatus
}>()

const statusConfig: Record<StudentStatus, { label: string; color: string; bg: string }> = {
  [StudentStatus.NOT_SUBMITTED]: {
    label: '未填报一轮志愿',
    color: 'var(--color-ink-subtle)',
    bg: 'var(--color-surface-3)',
  },
  [StudentStatus.WAITING_REVIEW]: {
    label: '一轮待筛选',
    color: 'var(--color-semantic-warning)',
    bg: 'var(--color-warning-bg)',
  },
  [StudentStatus.ACCEPTED]: {
    label: '一轮录取成功',
    color: 'var(--color-semantic-success)',
    bg: 'var(--color-success-bg)',
  },
  [StudentStatus.REJECTED]: {
    label: '一轮落选可报二轮',
    color: 'var(--color-semantic-error)',
    bg: 'var(--color-error-bg)',
  },
  [StudentStatus.ROUND2_MATCHED]: {
    label: '二轮匹配完成',
    color: 'var(--color-semantic-success)',
    bg: 'var(--color-success-bg)',
  },
  [StudentStatus.WAITING_ASSIGNMENT]: {
    label: '未匹配待分配',
    color: 'var(--color-semantic-warning)',
    bg: 'var(--color-warning-bg)',
  },
}

const config = computed(() => statusConfig[props.status])
</script>

<template>
  <div class="student-status-card">
    <div class="status-indicator" :style="{ background: config.color }" />
    <div class="status-icon" :style="{ background: config.bg }">
      <span :style="{ color: config.color }">●</span>
    </div>
    <div class="status-text">
      <div class="status-label">{{ config.label }}</div>
    </div>
  </div>
</template>

<style scoped>
.student-status-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  background: var(--color-card);
  border-radius: var(--rounded-lg);
  border: 1px solid var(--color-hairline);
  box-shadow: var(--shadow-card);
  padding: var(--spacing-lg);
  position: relative;
  overflow: hidden;
}

.status-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
}

.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--rounded-md);
  font-size: 20px;
}

.status-label {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink-muted);
}
</style>
