<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ImportLog } from '@/types'
import { ImportRowStatus } from '@/types'
import StatusBadge from './StatusBadge.vue'
import EmptyState from './EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getImportRowStatusBadge } from '@/utils/badges'

const props = defineProps<{
  logs: ImportLog[]
}>()

type FilterValue = 'ALL' | ImportRowStatus

const filter = ref<FilterValue>('ALL')

const filteredLogs = computed(() => {
  if (filter.value === 'ALL') return props.logs
  return props.logs.filter((l) => l.status === filter.value)
})

const filterOptions: { label: string; value: FilterValue }[] = [
  { label: '全部', value: 'ALL' },
  { label: '成功', value: ImportRowStatus.SUCCESS },
  { label: '失败', value: ImportRowStatus.FAILED },
]

/* 美化 JSON 行数据展示 */
function prettyRow(rowData: string): string {
  try {
    const obj = JSON.parse(rowData)
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${v}`)
      .join('  |  ')
  } catch {
    return rowData
  }
}

const hasLogs = computed(() => props.logs.length > 0)
</script>

<template>
  <div class="import-log-detail">
    <!-- 筛选 -->
    <div v-if="hasLogs" class="filter-bar">
      <el-radio-group v-model="filter" size="small">
        <el-radio-button v-for="opt in filterOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
      <span class="filter-count">共 {{ filteredLogs.length }} 条记录</span>
    </div>

    <div v-if="hasLogs && filteredLogs.length" class="log-table">
      <div class="table-header">
        <div class="col-row">行号</div>
        <div class="col-data">行数据</div>
        <div class="col-status">状态</div>
        <div class="col-reason">失败原因</div>
        <div class="col-time">导入时间</div>
      </div>
      <div
        v-for="log in filteredLogs"
        :key="log.id"
        :class="['table-row', { 'row-failed': log.status === ImportRowStatus.FAILED }]"
      >
        <div class="col-row">{{ log.rowNumber }}</div>
        <div class="col-data">{{ prettyRow(log.rowData) }}</div>
        <div class="col-status">
          <StatusBadge :variant="getImportRowStatusBadge(log.status).variant" :label="getImportRowStatusBadge(log.status).label" />
        </div>
        <div class="col-reason">{{ log.failReason ?? '—' }}</div>
        <div class="col-time">{{ formatDateTime(log.createdAt) }}</div>
      </div>
    </div>

    <EmptyState
      v-else
      title="暂无导入日志"
      description="该任务无导入日志记录"
    />
  </div>
</template>

<style scoped>
.import-log-detail {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.filter-count {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.log-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 70px 2fr 100px 1.4fr 1.2fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.table-row {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.table-row:last-child {
  border-bottom: none;
}

/* 失败行高亮 — DESIGN.md import-log-detail */
.row-failed {
  background: var(--color-error-bg);
  border-radius: var(--rounded-sm);
}

.col-data {
  word-break: break-all;
  font-family: var(--font-mono, monospace);
  font-size: var(--text-caption);
}

.col-reason {
  color: var(--color-semantic-error);
}

@media (max-width: 900px) {
  .table-header {
    display: none;
  }
  .table-row {
    grid-template-columns: 1fr 1fr;
    padding: var(--spacing-sm);
    border: 1px solid var(--color-hairline);
    border-radius: var(--rounded-md);
    margin-bottom: var(--spacing-sm);
  }
  .col-data {
    grid-column: 1 / -1;
  }
}
</style>
