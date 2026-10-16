<script setup lang="ts">
import { computed } from 'vue'
import type { SystemStateSchedule } from '@/types'
import { SystemState } from '@/types'
import AppButton from './AppButton.vue'
import AppToggle from './AppToggle.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  schedule: SystemStateSchedule
  currentState: SystemState
  stateLabels: Record<string, string>
}>()
const emit = defineEmits<{
  (e: 'update:field', field: keyof SystemStateSchedule, value: string | null): void
  (e: 'toggle-auto', enabled: boolean): void
}>()

interface ConfigRow {
  field: keyof SystemStateSchedule
  label: string
  fromState: SystemState
  toState: SystemState
}

const rows: ConfigRow[] = [
  {
    field: 'firstRoundStartAt',
    label: '第一轮开始',
    fromState: SystemState.INIT,
    toState: SystemState.FIRST_ROUND_OPEN,
  },
  {
    field: 'firstRoundEndAt',
    label: '第一轮结束',
    fromState: SystemState.FIRST_ROUND_OPEN,
    toState: SystemState.TEACHER_REVIEW,
  },
  {
    field: 'teacherReviewEndAt',
    label: '导师筛选结束',
    fromState: SystemState.TEACHER_REVIEW,
    toState: SystemState.SECOND_ROUND_OPEN,
  },
  {
    field: 'secondRoundEndAt',
    label: '第二轮结束',
    fromState: SystemState.SECOND_ROUND_OPEN,
    toState: SystemState.AUTO_ASSIGN,
  },
]

/* 转换点状态：已配置 / 未配置 / 已执行 */
function rowStatus(row: ConfigRow): { variant: 'success' | 'warning' | 'default'; label: string } {
  const value = props.schedule[row.field] as string | null
  if (!value) return { variant: 'default', label: '未配置' }
  /* 若 fromState 已超过 currentState，则视为已执行 */
  const order = [
    SystemState.INIT,
    SystemState.FIRST_ROUND_OPEN,
    SystemState.TEACHER_REVIEW,
    SystemState.SECOND_ROUND_OPEN,
    SystemState.AUTO_ASSIGN,
    SystemState.FINISHED,
  ]
  const fromIdx = order.indexOf(row.fromState)
  const currentIdx = order.indexOf(props.currentState)
  if (fromIdx < currentIdx) return { variant: 'success', label: '已执行' }
  return { variant: 'warning', label: '已配置' }
}

/* datetime-local 值转换 */
function fieldValue(row: ConfigRow): string {
  const v = props.schedule[row.field] as string | null
  if (!v) return ''
  /* ISO → datetime-local 格式 */
  return v.slice(0, 16)
}

function handleInput(row: ConfigRow, value: string) {
  emit('update:field', row.field, value ? new Date(value).toISOString() : null)
}

function handleClear(row: ConfigRow) {
  emit('update:field', row.field, null)
}

const autoEnabled = computed(() => props.schedule.autoEnabled)

function handleToggleAuto(value: boolean) {
  emit('toggle-auto', value)
}
</script>

<template>
  <div class="schedule-config">
    <!-- 顶部全局开关 -->
    <div class="config-header">
      <div class="config-header-info">
        <span class="config-header-title">自动切换</span>
        <span class="config-header-hint">
          启用后，到达计划时间将自动推进系统状态
        </span>
      </div>
      <AppToggle
        :model-value="autoEnabled"
        @update:model-value="handleToggleAuto"
      />
    </div>

    <!-- 配置表 -->
    <div class="config-table">
      <div class="table-header">
        <div class="col-transition">转换点</div>
        <div class="col-time">计划时间</div>
        <div class="col-status">状态</div>
        <div class="col-action">操作</div>
      </div>
      <div v-for="row in rows" :key="row.field" class="table-row">
        <div class="col-transition">
          <div class="transition-label">{{ row.label }}</div>
          <div class="transition-flow">
            {{ stateLabels[row.fromState] }} → {{ stateLabels[row.toState] }}
          </div>
        </div>
        <div class="col-time">
          <el-date-picker
            :model-value="fieldValue(row)"
            type="datetime-local"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm"
            placeholder="选择时间"
            size="small"
            :disabled="!autoEnabled"
            @update:model-value="(v: string) => handleInput(row, v ?? '')"
          />
        </div>
        <div class="col-status">
          <StatusBadge :variant="rowStatus(row).variant" :label="rowStatus(row).label" />
        </div>
        <div class="col-action">
          <AppButton
            variant="tertiary"
            :disabled="!autoEnabled || !fieldValue(row)"
            @click="handleClear(row)"
          >
            清除
          </AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.schedule-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-surface-2);
  border-radius: var(--rounded-md);
}

.config-header-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.config-header-title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
}

.config-header-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.config-table {
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  overflow: hidden;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1.4fr 1.6fr 110px 100px;
  gap: var(--spacing-sm);
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
}

.table-header {
  background: var(--color-surface-2);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.table-row {
  border-top: 1px solid var(--color-hairline);
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.col-transition {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.transition-label {
  font-weight: 500;
  color: var(--color-ink);
}

.transition-flow {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

@media (max-width: 760px) {
  .table-header {
    display: none;
  }
  .table-row {
    grid-template-columns: 1fr 1fr;
    padding: var(--spacing-md);
  }
  .col-action {
    grid-column: 1 / -1;
  }
}
</style>
