<script setup lang="ts">
import { computed } from 'vue'
import { Calendar, Check, Close, Lock } from '@element-plus/icons-vue'
import type { AcademicYear } from '@/types'
import { AcademicYearStatus, SystemState } from '@/types'
import AppButton from './AppButton.vue'
import StatusBadge from './StatusBadge.vue'
import { useAdminStore } from '@/stores/admin'
import { formatDateTime } from '@/composables/useFormatTime'

const props = defineProps<{
  year: AcademicYear
}>()
const emit = defineEmits<{
  (e: 'activate', id: number): void
  (e: 'close', id: number): void
}>()

const adminStore = useAdminStore()

/* 卡片变体（左竖条颜色） */
const variant = computed(() => {
  switch (props.year.status) {
    case AcademicYearStatus.ACTIVE:
      return 'active'
    case AcademicYearStatus.CLOSED:
      return 'closed'
    case AcademicYearStatus.DRAFT:
      return 'draft'
    default:
      return 'draft'
  }
})

const statusBadge = computed<{ variant: 'success' | 'warning' | 'default'; label: string }>(() => {
  switch (props.year.status) {
    case AcademicYearStatus.ACTIVE:
      return { variant: 'success', label: '进行中' }
    case AcademicYearStatus.CLOSED:
      return { variant: 'default', label: '已结束' }
    case AcademicYearStatus.DRAFT:
      return { variant: 'warning', label: '草稿' }
    default:
      return { variant: 'default', label: '—' }
  }
})

const isActive = computed(() => props.year.status === AcademicYearStatus.ACTIVE)
const isDraft = computed(() => props.year.status === AcademicYearStatus.DRAFT)
/* R9-05：仅 FINISHED 状态可关闭 ACTIVE 学年 */
const canClose = computed(
  () => isActive.value && adminStore.systemState === SystemState.FINISHED,
)

function handleActivate() {
  emit('activate', props.year.id)
}
function handleClose() {
  emit('close', props.year.id)
}
</script>

<template>
  <div :class="['year-card', `year-card-${variant}`]">
    <div class="year-card-accent" />

    <div class="year-card-body">
      <!-- 顶部：名称 + 状态徽章 -->
      <div class="year-card-header">
        <h3 class="year-card-title">{{ year.name }}</h3>
        <StatusBadge :variant="statusBadge.variant" :label="statusBadge.label" />
      </div>

      <!-- 中部：时间信息 -->
      <div class="year-card-meta">
        <div class="meta-item">
          <el-icon class="meta-icon"><Calendar /></el-icon>
          <span class="meta-label">开始年份</span>
          <span class="meta-value">{{ year.startYear }}</span>
        </div>
        <div class="meta-item">
          <el-icon class="meta-icon"><Calendar /></el-icon>
          <span class="meta-label">结束年份</span>
          <span class="meta-value">{{ year.endYear }}</span>
        </div>
        <div class="meta-item">
          <el-icon class="meta-icon"><Check /></el-icon>
          <span class="meta-label">激活时间</span>
          <span class="meta-value">{{ formatDateTime(year.activatedAt ?? undefined) }}</span>
        </div>
        <div class="meta-item">
          <el-icon class="meta-icon"><Lock /></el-icon>
          <span class="meta-label">关闭时间</span>
          <span class="meta-value">{{ formatDateTime(year.closedAt ?? undefined) }}</span>
        </div>
      </div>

      <!-- 底部：操作按钮 -->
      <div class="year-card-actions">
        <AppButton v-if="isDraft" variant="primary" @click="handleActivate">
          激活学年
        </AppButton>
        <AppButton
          v-if="isActive"
          variant="danger"
          :disabled="!canClose"
          @click="handleClose"
        >
          关闭学年
        </AppButton>
        <span v-if="isActive && !canClose" class="year-card-hint">
          <el-icon><Close /></el-icon>
          系统状态非「结束」，暂无法关闭
        </span>
        <span v-else-if="variant === 'closed'" class="year-card-hint">
          历史学年，只读
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.year-card {
  position: relative;
  display: flex;
  background: var(--color-card);
  color: var(--color-ink);
  border-radius: var(--rounded-lg);
  border: 1px solid var(--color-hairline);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.year-card-accent {
  width: 4px;
  flex-shrink: 0;
}

.year-card-active .year-card-accent {
  background: var(--color-primary);
}
.year-card-closed .year-card-accent {
  background: var(--color-ink-tertiary);
}
.year-card-draft .year-card-accent {
  background: var(--color-ink-subtle);
}

.year-card-body {
  flex: 1;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.year-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.year-card-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
  margin: 0;
}

.year-card-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm) var(--spacing-md);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--text-body-sm);
}

.meta-icon {
  color: var(--color-ink-subtle);
  font-size: 14px;
}

.meta-label {
  color: var(--color-ink-subtle);
}

.meta-value {
  color: var(--color-ink);
  font-weight: 500;
}

.year-card-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
}

.year-card-hint {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--text-caption);
  color: var(--color-ink-tertiary);
}

@media (max-width: 600px) {
  .year-card-meta {
    grid-template-columns: 1fr;
  }
}
</style>
