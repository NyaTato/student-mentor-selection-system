<script setup lang="ts">
import { computed } from 'vue'
import { useStudentStore } from '@/stores/student'
import { ApplicationStatus } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const studentStore = useStudentStore()

/* 当前学生的第一轮申请 */
const application = computed(() => studentStore.myFirstRoundApplication)

/* 申请对应的导师信息 */
const teacher = computed(() => {
  const app = application.value
  if (!app) return undefined
  return studentStore.getTeacherById(app.teacherId)
})

/* 状态映射：PENDING → 待筛选(warning), ACCEPTED → 录取成功(success), REJECTED → 未录取(error) */
interface StatusDisplay {
  label: string
  variant: 'warning' | 'success' | 'error' | 'default'
}

const statusDisplay = computed<StatusDisplay>(() => {
  const status = application.value?.status
  switch (status) {
    case ApplicationStatus.PENDING:
      return { label: '待筛选', variant: 'warning' }
    case ApplicationStatus.ACCEPTED:
      return { label: '录取成功', variant: 'success' }
    case ApplicationStatus.REJECTED:
      return { label: '未录取', variant: 'error' }
    default:
      return { label: '未知', variant: 'default' }
  }
})

/* 是否已录取 */
const isAccepted = computed(
  () => application.value?.status === ApplicationStatus.ACCEPTED,
)

/* 是否被拒绝 */
const isRejected = computed(
  () => application.value?.status === ApplicationStatus.REJECTED,
)
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">一轮结果</h1>
    <p class="page-description">查看第一轮审核结果</p>

    <!-- 有申请：展示志愿及审核结果 -->
    <AppCard v-if="application && teacher" variant="default">
      <!-- 状态行 -->
      <div class="status-row">
        <span class="row-label">审核状态</span>
        <StatusBadge
          :label="statusDisplay.label"
          :variant="statusDisplay.variant"
        />
      </div>

      <!-- 导师信息 -->
      <div class="info-block">
        <h2 class="teacher-name">{{ teacher.name }}</h2>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-key">学院</span>
            <span class="info-val">{{ teacher.department }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">职称</span>
            <span class="info-val">{{ teacher.title }}</span>
          </div>
          <div class="info-item info-item-full">
            <span class="info-key">研究方向</span>
            <span class="info-val">{{ teacher.researchArea }}</span>
          </div>
        </div>
      </div>

      <!-- 结果提示信息 -->
      <div v-if="isAccepted" class="alert alert-success">
        恭喜！您已被录取
      </div>
      <div v-else-if="isRejected" class="alert alert-error">
        您在第一轮未被录取，可参加第二轮先到先得报名
      </div>
    </AppCard>

    <!-- 无申请：空状态 -->
    <EmptyState
      v-else
      title="暂无申请记录"
      description="您在第一轮未提交志愿申请"
    />
  </div>
</template>

<style scoped>
.page-container {
  max-width: 720px;
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

/* 状态行 */
.status-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding-bottom: var(--spacing-md);
  margin-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-hairline);
}

.row-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

/* 导师信息块 */
.info-block {
  margin-bottom: var(--spacing-md);
}

.teacher-name {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
  margin-bottom: var(--spacing-md);
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

.info-item-full {
  grid-column: 1 / -1;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-key {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-val {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

/* 结果提示横幅 */
.alert {
  font-size: var(--text-body-sm);
  border-radius: var(--rounded-md);
  padding: var(--spacing-sm) var(--spacing-md);
  margin-top: var(--spacing-md);
  border: 1px solid;
}

.alert-success {
  background: var(--color-success-bg);
  color: var(--color-semantic-success);
  border-color: var(--color-success-border);
}

.alert-error {
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
  border-color: var(--color-error-border);
}

/* 响应式：窄屏单列 */
@media (max-width: 600px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
