<script setup lang="ts">
import { WarningFilled } from '@element-plus/icons-vue'
import AppCard from './AppCard.vue'
import AppButton from './AppButton.vue'
import StatusBadge from './StatusBadge.vue'
import QuotaBadge from './QuotaBadge.vue'

interface PreviewTeacher {
  id: number
  name: string
  teacherNumber: string
  department: string
  title: string
  remaining: number
  maxQuota: number
  currentAdmitted: number
}

defineProps<{
  totalCandidates: number
  assignableCount: number
  totalRemaining: number
  isInsufficient: boolean
  topTeachers: PreviewTeacher[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()
</script>

<template>
  <AppCard variant="default">
    <div class="preview-content">
      <!-- 顶部：未匹配学生数 -->
      <div class="preview-header">
        <span class="preview-eyebrow">未匹配学生</span>
        <span class="preview-count">{{ totalCandidates }}</span>
        <span class="preview-label">预计可分配</span>
        <span class="preview-assignable">{{ assignableCount }}</span>
      </div>

      <!-- 名额不足警告 -->
      <div v-if="isInsufficient" class="preview-warning">
        <el-icon class="warning-icon"><WarningFilled /></el-icon>
        <div class="warning-body">
          <StatusBadge variant="error" label="名额不足" />
          <p class="warning-text">
            导师总剩余名额（{{ totalRemaining }}）少于未匹配学生数（{{ totalCandidates }}），将暂停分配并告警。
          </p>
        </div>
      </div>

      <!-- 中部：可分配导师列表（前 5 名） -->
      <div class="preview-teachers">
        <h4 class="preview-section-title">可分配导师（按剩余名额降序，前 5 名）</h4>
        <div v-if="topTeachers.length" class="teacher-list">
          <div v-for="t in topTeachers" :key="t.id" class="teacher-item">
            <div class="teacher-info">
              <span class="teacher-name">{{ t.name }}</span>
              <span class="teacher-meta">{{ t.department }} · {{ t.title }}</span>
            </div>
            <QuotaBadge :admitted="t.currentAdmitted" :max="t.maxQuota" />
          </div>
        </div>
        <p v-else class="no-teachers">暂无可分配导师</p>
      </div>

      <!-- 底部：操作按钮 -->
      <div class="preview-actions">
        <AppButton variant="secondary" @click="emit('cancel')">取消</AppButton>
        <AppButton
          variant="primary"
          :disabled="loading || totalCandidates === 0 || topTeachers.length === 0"
          @click="emit('confirm')"
        >
          {{ loading ? '分配中…' : '确认执行自动分配' }}
        </AppButton>
      </div>
    </div>
  </AppCard>
</template>

<style scoped>
.preview-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.preview-header {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.preview-eyebrow {
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  letter-spacing: var(--text-eyebrow-spacing);
  color: var(--color-ink-subtle);
  text-transform: uppercase;
}

.preview-count {
  font-size: var(--text-display-md);
  font-weight: var(--text-display-md-weight);
  line-height: var(--text-display-md-line);
  color: var(--color-ink);
}

.preview-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
  margin-left: var(--spacing-sm);
}

.preview-assignable {
  font-size: var(--text-headline);
  font-weight: 600;
  color: var(--color-primary);
}

.preview-warning {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-error-bg);
  border-radius: var(--rounded-md);
}

.warning-icon {
  font-size: 20px;
  color: var(--color-semantic-error);
  flex-shrink: 0;
}

.warning-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.warning-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.preview-teachers {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.preview-section-title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.teacher-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.teacher-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-surface-2);
  border-radius: var(--rounded-sm);
}

.teacher-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-name {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.teacher-meta {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.no-teachers {
  font-size: var(--text-body-sm);
  color: var(--color-ink-tertiary);
  padding: var(--spacing-sm);
  text-align: center;
}

.preview-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
}
</style>
