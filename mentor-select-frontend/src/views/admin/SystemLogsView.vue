<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { LogType } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StatItem from '@/components/base/StatItem.vue'
import FilterTabs from '@/components/base/FilterTabs.vue'
import { formatTimeWithSeconds } from '@/composables/useFormatTime'

const adminStore = useAdminStore()

/* 筛选 */
type LogFilter = 'ALL' | LogType
const logFilter = ref<LogFilter>('ALL')

const filteredLogs = computed(() => {
  if (logFilter.value === 'ALL') return adminStore.logs
  return adminStore.logs.filter((l) => l.type === logFilter.value)
})

/* 搜索 */
const searchKeyword = ref('')
const searchedLogs = computed(() => {
  if (!searchKeyword.value.trim()) return filteredLogs.value
  const kw = searchKeyword.value.toLowerCase()
  return filteredLogs.value.filter(
    (l) =>
      l.operator.toLowerCase().includes(kw) ||
      l.action.toLowerCase().includes(kw) ||
      (l.target?.toLowerCase().includes(kw) ?? false),
  )
})

/* 统计 */
const stats = computed(() => ({
  total: adminStore.logs.length,
  login: adminStore.logs.filter((l) => l.type === LogType.LOGIN).length,
  operation: adminStore.logs.filter((l) => l.type === LogType.OPERATION).length,
  error: adminStore.logs.filter((l) => l.type === LogType.ERROR).length,
}))

function getLogTypeBadge(type: LogType) {
  switch (type) {
    case LogType.LOGIN:
      return { variant: 'default' as const, label: '登录日志' }
    case LogType.OPERATION:
      return { variant: 'success' as const, label: '操作日志' }
    case LogType.ERROR:
      return { variant: 'error' as const, label: '异常日志' }
    default:
      return { variant: 'default' as const, label: '未知' }
  }
}

const filterOptions: { label: string; value: LogFilter }[] = [
  { label: '全部', value: 'ALL' },
  { label: '登录日志', value: LogType.LOGIN },
  { label: '操作日志', value: LogType.OPERATION },
  { label: '异常日志', value: LogType.ERROR },
]
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">系统日志</h1>
    <p class="page-description">查看登录日志、操作日志、异常日志</p>

    <!-- 统计 -->
    <div class="stats-grid">
      <AppCard variant="compact">
        <StatItem label="日志总数" :value="stats.total" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="登录日志" :value="stats.login" tone="info" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="操作日志" :value="stats.operation" tone="success" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="异常日志" :value="stats.error" tone="error" />
      </AppCard>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        class="search-input"
        placeholder="搜索操作人/操作内容"
        clearable
      />
      <FilterTabs v-model="logFilter" :options="filterOptions" />
    </div>

    <!-- 日志表格 -->
    <AppCard variant="default">
      <div v-if="searchedLogs.length" class="log-table">
        <div class="log-table-header">
          <div class="col-type">类型</div>
          <div class="col-operator">操作人</div>
          <div class="col-action">操作内容</div>
          <div class="col-target">操作对象</div>
          <div class="col-ip">IP 地址</div>
          <div class="col-time">时间</div>
        </div>
        <div v-for="log in searchedLogs" :key="log.id" class="log-table-row">
          <div class="col-type">
            <StatusBadge
              :variant="getLogTypeBadge(log.type).variant"
              :label="getLogTypeBadge(log.type).label"
            />
          </div>
          <div class="col-operator">{{ log.operator }}</div>
          <div class="col-action">
            <span class="action-text">{{ log.action }}</span>
            <span v-if="log.detail" class="action-detail">{{ log.detail }}</span>
          </div>
          <div class="col-target">{{ log.target ?? '-' }}</div>
          <div class="col-ip">{{ log.ip }}</div>
          <div class="col-time">{{ formatTimeWithSeconds(log.timestamp) }}</div>
        </div>
      </div>
      <EmptyState v-else title="暂无日志记录" />
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
}

.page-title {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
  margin-bottom: var(--spacing-xs);
}

.page-description {
  font-size: var(--text-body);
  color: var(--color-ink-muted);
  margin-bottom: var(--spacing-lg);
}

/* 统计 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.search-input {
  flex: 1;
  max-width: 320px;
}

/* 表格 */
.log-table {
  display: flex;
  flex-direction: column;
}

.log-table-header,
.log-table-row {
  display: grid;
  grid-template-columns: 0.9fr 0.9fr 1.8fr 1fr 1fr 1.4fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.log-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.log-table-row {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.log-table-row:last-child { border-bottom: none; }

.col-operator {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.col-action {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.action-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.action-detail {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.col-target,
.col-ip {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.col-time {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-input { max-width: none; }
}
</style>
