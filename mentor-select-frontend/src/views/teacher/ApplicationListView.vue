<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTeacherStore } from '@/stores/teacher'
import { SystemState, ApplicationStatus } from '@/types'
import { InfoFilled } from '@element-plus/icons-vue'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import FilterTabs from '@/components/base/FilterTabs.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getApplicationStatusBadge } from '@/utils/badges'

const teacherStore = useTeacherStore()

/* 仅在导师筛选阶段允许录取/拒绝操作（R2-04 / R2-07 / R2-08） */
const canReview = computed(() => teacherStore.systemState === SystemState.TEACHER_REVIEW)

/* 筛选状态 */
type FilterStatus = 'ALL' | ApplicationStatus
const filterStatus = ref<FilterStatus>('ALL')

const filteredApplications = computed(() => {
  const list = teacherStore.myApplications
  if (filterStatus.value === 'ALL') return list
  return list.filter((a) => a.status === filterStatus.value)
})

/* 名额信息 */
const quota = computed(() => teacherStore.quotaInfo)

/* 是否已达名额上限（R2-05） */
const isQuotaFull = computed(() => quota.value.remaining <= 0)

function getStudent(id: number) {
  return teacherStore.getStudentById(id)
}


/* 录取学生 — 强制名额校验（R2-01 / R2-05） */
function handleAdmit(applicationId: number) {
  if (isQuotaFull.value) {
    alert('已达招生名额上限，无法继续录取')
    return
  }
  teacherStore.admitStudent(applicationId)
}

/* 拒绝学生 */
function handleReject(applicationId: number) {
  if (!confirm('确认拒绝该学生申请？')) return
  teacherStore.rejectStudent(applicationId)
}

const filterOptions: { label: string; value: FilterStatus }[] = [
  { label: '全部', value: 'ALL' },
  { label: '待审核', value: ApplicationStatus.PENDING },
  { label: '已录取', value: ApplicationStatus.ACCEPTED },
  { label: '已拒绝', value: ApplicationStatus.REJECTED },
]
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">申请列表</h1>
    <p class="page-description">查看申请你的学生并进行筛选</p>

    <!-- 名额提示 -->
    <AppCard variant="compact" :class="['quota-banner', { 'quota-banner-full': isQuotaFull }]">
      <div class="quota-banner-content">
        <span class="quota-text">
          招生名额：{{ quota.max }}｜已录取：{{ quota.admitted }}｜剩余：{{ quota.remaining }}
        </span>
        <span v-if="isQuotaFull" class="quota-warning">已达名额上限</span>
      </div>
    </AppCard>

    <!-- 阶段提示 -->
    <StateNotice v-if="!canReview" :icon="InfoFilled">
      当前非导师筛选阶段，仅可查看申请，不可操作录取/拒绝
    </StateNotice>

    <!-- 筛选 -->
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">状态筛选</span>
        <FilterTabs v-model="filterStatus" :options="filterOptions" />
      </div>
    </div>

    <!-- 申请列表 -->
    <AppCard variant="default">
      <div v-if="filteredApplications.length" class="app-table">
        <div class="app-table-header">
          <div class="col-student">学生</div>
          <div class="col-major">专业</div>
          <div class="col-time">申请时间</div>
          <div class="col-status">状态</div>
          <div class="col-action">操作</div>
        </div>
        <div v-for="app in filteredApplications" :key="app.id" class="app-table-row">
          <div class="col-student">
            <div class="student-name">{{ getStudent(app.studentId)?.name ?? '未知' }}</div>
            <div class="student-id">{{ getStudent(app.studentId)?.studentId ?? '-' }}</div>
          </div>
          <div class="col-major">{{ getStudent(app.studentId)?.major ?? '-' }}</div>
          <div class="col-time">{{ formatDateTime(app.createdAt) }}</div>
          <div class="col-status">
            <StatusBadge
              :variant="getApplicationStatusBadge(app.status).variant"
              :label="getApplicationStatusBadge(app.status).label"
            />
          </div>
          <div class="col-action">
            <template v-if="canReview && app.status === ApplicationStatus.PENDING">
              <AppButton
                variant="primary"
                :disabled="isQuotaFull"
                @click="handleAdmit(app.id)"
              >
                录取
              </AppButton>
              <AppButton variant="danger" @click="handleReject(app.id)">拒绝</AppButton>
            </template>
            <span v-else class="action-readonly">—</span>
          </div>
        </div>
      </div>
      <EmptyState v-else title="暂无符合条件的学生申请" />
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1100px;
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

/* 名额横幅 */
.quota-banner {
  margin-bottom: var(--spacing-md);
  background: var(--color-surface-1);
}

.quota-banner-full {
  background: var(--color-error-bg);
}

.quota-banner-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.quota-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.quota-warning {
  font-size: var(--text-caption);
  color: var(--color-semantic-error);
  font-weight: 600;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.filter-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

/* 表格 */
.app-table {
  display: flex;
  flex-direction: column;
}

.app-table-header,
.app-table-row {
  display: grid;
  grid-template-columns: 1.5fr 1.5fr 1.5fr 1fr 1.5fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.app-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.app-table-row {
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.app-table-row:last-child {
  border-bottom: none;
}

.col-student {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.student-name {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.student-id {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.col-major,
.col-time {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.col-action {
  display: flex;
  gap: var(--spacing-xs);
}

.action-readonly {
  color: var(--color-ink-tertiary);
}
</style>
