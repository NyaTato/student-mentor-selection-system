<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { SystemState, AssignmentSource } from '@/types'
import { InfoFilled } from '@element-plus/icons-vue'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import StatItem from '@/components/base/StatItem.vue'
import FilterTabs from '@/components/base/FilterTabs.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAssignmentSourceBadge } from '@/utils/badges'

const adminStore = useAdminStore()

/* 系统完成后才显示最终分配结果（PROJECT.md 7.7） */
const isFinished = computed(() => adminStore.systemState === SystemState.FINISHED)

const results = computed(() => adminStore.assignmentResults)

/* 筛选 */
type SourceFilter = 'ALL' | AssignmentSource
const sourceFilter = ref<SourceFilter>('ALL')

const filteredResults = computed(() => {
  if (sourceFilter.value === 'ALL') return results.value
  return results.value.filter((r) => r.source === sourceFilter.value)
})

/* 搜索 */
const searchKeyword = ref('')
const searchedResults = computed(() => {
  if (!searchKeyword.value.trim()) return filteredResults.value
  const kw = searchKeyword.value.toLowerCase()
  return filteredResults.value.filter(
    (r) =>
      r.studentName.toLowerCase().includes(kw) ||
      r.studentNumber.toLowerCase().includes(kw) ||
      r.teacherName.toLowerCase().includes(kw),
  )
})

/* 统计 */
const stats = computed(() => ({
  total: results.value.length,
  round1: results.value.filter((r) => r.source === AssignmentSource.ROUND1).length,
  round2: results.value.filter((r) => r.source === AssignmentSource.ROUND2).length,
  manual: results.value.filter((r) => r.source === AssignmentSource.MANUAL).length,
  auto: results.value.filter((r) => r.source === AssignmentSource.AUTO_ASSIGNED).length,
}))

/* 导出 CSV */
function handleExport() {
  const headers = ['学号', '姓名', '专业', '院系', '导师姓名', '导师院系', '分配来源', '分配时间']
  const rows = searchedResults.value.map((r) => [
    r.studentNumber,
    r.studentName,
    r.major,
    r.department,
    r.teacherName,
    r.teacherDepartment,
    r.source,
    formatDateTime(r.assignedAt),
  ])
  const csv = [headers, ...rows].map((row) => row.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'assignment-results.csv'
  link.click()
  URL.revokeObjectURL(url)
}

const filterOptions: { label: string; value: SourceFilter }[] = [
  { label: '全部', value: 'ALL' },
  { label: '第一轮', value: AssignmentSource.ROUND1 },
  { label: '第二轮', value: AssignmentSource.ROUND2 },
  { label: '管理员分配', value: AssignmentSource.MANUAL },
  { label: '系统自动分配', value: AssignmentSource.AUTO_ASSIGNED },
]
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">分配结果</h1>
        <p class="page-description">最终导师分配结果总表</p>
      </div>
      <AppButton v-if="searchedResults.length" variant="secondary" @click="handleExport">
        导出 CSV
      </AppButton>
    </div>

    <!-- 阶段提示 -->
    <StateNotice v-if="!isFinished" :icon="InfoFilled">
      系统尚未结束，当前结果可能仍会变化
    </StateNotice>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <AppCard variant="compact">
        <StatItem label="总分配数" :value="stats.total" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="第一轮录取" :value="stats.round1" tone="success" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="第二轮匹配" :value="stats.round2" tone="warning" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="管理员分配" :value="stats.manual" tone="info" />
      </AppCard>
      <AppCard variant="compact">
        <StatItem label="系统自动分配" :value="stats.auto" tone="success" />
      </AppCard>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        class="search-input"
        placeholder="搜索学号/姓名/导师"
        clearable
      />
      <FilterTabs v-model="sourceFilter" :options="filterOptions" />
    </div>

    <!-- 结果表格 -->
    <AppCard variant="default">
      <div v-if="searchedResults.length" class="result-table">
        <div class="result-table-header">
          <div class="col-student">学生</div>
          <div class="col-major">专业</div>
          <div class="col-department">院系</div>
          <div class="col-teacher">导师</div>
          <div class="col-source">分配来源</div>
          <div class="col-time">分配时间</div>
        </div>
        <div v-for="item in searchedResults" :key="item.admissionId" class="result-table-row">
          <div class="col-student">
            <div class="student-name">{{ item.studentName }}</div>
            <div class="student-id">{{ item.studentNumber }}</div>
          </div>
          <div class="col-major">{{ item.major }}</div>
          <div class="col-department">{{ item.department }}</div>
          <div class="col-teacher">
            <div class="teacher-name">{{ item.teacherName }}</div>
            <div class="teacher-dept">{{ item.teacherDepartment }}</div>
          </div>
          <div class="col-source">
            <StatusBadge
              :variant="getAssignmentSourceBadge(item.source).variant"
              :label="getAssignmentSourceBadge(item.source).label"
            />
          </div>
          <div class="col-time">{{ formatDateTime(item.assignedAt) }}</div>
        </div>
      </div>
      <EmptyState v-else title="暂无分配结果" />
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
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
}

/* 统计 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
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
.result-table {
  display: flex;
  flex-direction: column;
}

.result-table-header,
.result-table-row {
  display: grid;
  grid-template-columns: 1.4fr 1.2fr 1fr 1.4fr 1fr 1.4fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.result-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.result-table-row {
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.result-table-row:last-child { border-bottom: none; }

.col-student,
.col-teacher {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.student-name,
.teacher-name {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.student-id,
.teacher-dept {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.col-major,
.col-department,
.col-time {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

@media (max-width: 1100px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-input { max-width: none; }
}
</style>
