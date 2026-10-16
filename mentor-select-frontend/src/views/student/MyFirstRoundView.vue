<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import { ApplicationStatus } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'

const studentStore = useStudentStore()
const router = useRouter()

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

/* 是否修改过 */
const isModified = computed(() => {
  const app = application.value
  if (!app) return false
  return app.updatedAt !== app.createdAt
})

function goModify() {
  router.push('/student/first-round/apply')
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">我的志愿</h1>
    <p class="page-description">查看和修改第一轮申请</p>

    <!-- 有申请：展示志愿详情 -->
    <AppCard v-if="application && teacher" variant="default">
      <!-- 状态行 -->
      <div class="status-row">
        <span class="row-label">当前状态</span>
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

      <!-- 申请时间 -->
      <div class="time-grid">
        <div class="info-item">
          <span class="info-key">申请时间</span>
          <span class="info-val">{{ formatDateTime(application.createdAt) }}</span>
        </div>
        <div v-if="isModified" class="info-item">
          <span class="info-key">最近修改</span>
          <span class="info-val">{{ formatDateTime(application.updatedAt) }}</span>
        </div>
      </div>

      <!-- 操作 -->
      <div class="actions">
        <AppButton variant="primary" @click="goModify">修改志愿</AppButton>
      </div>
    </AppCard>

    <!-- 无申请：空状态 -->
    <EmptyState
      v-else
      title="暂未提交志愿"
      description="请在第一轮填报开放期间选择导师并提交志愿"
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

/* 时间网格 */
.time-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-bottom: var(--spacing-md);
}

/* 操作区 */
.actions {
  display: flex;
  justify-content: flex-start;
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
}

/* 响应式：窄屏单列 */
@media (max-width: 600px) {
  .info-grid,
  .time-grid {
    grid-template-columns: 1fr;
  }
}
</style>
