<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useStudentStore } from '@/stores/student'
import { ApplicationStatus, SystemState } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'

const studentStore = useStudentStore()
const router = useRouter()

/* 当前学生的第二轮申请 */
const application = computed(() => studentStore.mySecondRoundApplication)

/* 申请对应的导师信息 */
const teacher = computed(() => {
  const app = application.value
  if (!app) return undefined
  return studentStore.getTeacherById(app.teacherId)
})

/* 状态映射：ACCEPTED → 匹配完成(success), CANCELLED → 已取消(error) */
interface StatusDisplay {
  label: string
  variant: 'success' | 'error' | 'default'
}

const statusDisplay = computed<StatusDisplay>(() => {
  const status = application.value?.status
  switch (status) {
    case ApplicationStatus.ACCEPTED:
      return { label: '匹配完成', variant: 'success' }
    case ApplicationStatus.CANCELLED:
      return { label: '已取消', variant: 'error' }
    default:
      return { label: '未知', variant: 'default' }
  }
})

/* 是否匹配完成（ACCEPTED） */
const isMatched = computed(
  () => application.value?.status === ApplicationStatus.ACCEPTED,
)

/* 是否已取消（CANCELLED） */
const isCancelled = computed(
  () => application.value?.status === ApplicationStatus.CANCELLED,
)

/* 是否可取消：第二轮开放且已匹配，但系统未 FINISHED */
const canCancel = computed(
  () =>
    isMatched.value &&
    studentStore.systemState === SystemState.SECOND_ROUND_OPEN,
)

/* 是否只读（FINISHED 阶段，匹配完成后不可撤销） */
const isReadonly = computed(
  () => isMatched.value && !canCancel.value,
)

/* 跳转到第二轮导师列表 */
function goSelectTeacher() {
  router.push('/student/second-round/teachers')
}

/* 取消第二轮申请 */
async function handleCancel() {
  const result = await studentStore.cancelSecondRoundApplication()
  if (result.success) {
    ElMessage.success(result.message)
  } else {
    ElMessage.warning(result.message)
  }
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">我的二轮申请</h1>
    <p class="page-description">查看第二轮申请状态</p>

    <!-- 有申请：展示申请详情 -->
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
        <div v-if="application.updatedAt !== application.createdAt" class="info-item">
          <span class="info-key">最近更新</span>
          <span class="info-val">{{ formatDateTime(application.updatedAt) }}</span>
        </div>
      </div>

      <!-- 匹配完成且只读（FINISHED 阶段） -->
      <div v-if="isReadonly" class="alert alert-success">
        匹配完成，不可撤销
      </div>

      <!-- 已取消：可重新选择 -->
      <div v-else-if="isCancelled" class="alert alert-error">
        已取消，可重新选择其他导师
      </div>

      <!-- 操作区 -->
      <div class="actions">
        <!-- 已匹配且第二轮开放：允许取消 -->
        <AppButton
          v-if="canCancel"
          variant="danger"
          @click="handleCancel"
        >
          取消申请
        </AppButton>

        <!-- 已取消：可重新选择导师 -->
        <AppButton
          v-if="isCancelled"
          variant="primary"
          @click="goSelectTeacher"
        >
          选择导师
        </AppButton>
      </div>
    </AppCard>

    <!-- 无申请：空状态 -->
    <EmptyState
      v-else
      title="暂未提交第二轮申请"
      description="请在第二轮报名开放期间选择有余额的导师"
    >
      <div class="empty-actions">
        <AppButton variant="primary" @click="goSelectTeacher">
          选择导师
        </AppButton>
      </div>
    </EmptyState>
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

/* 提示横幅 */
.alert {
  font-size: var(--text-body-sm);
  border-radius: var(--rounded-md);
  padding: var(--spacing-sm) var(--spacing-md);
  margin-bottom: var(--spacing-md);
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

/* 操作区 */
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
}

/* 空状态按钮容器 */
.empty-actions {
  margin-top: var(--spacing-md);
}

/* 响应式：窄屏单列 */
@media (max-width: 600px) {
  .info-grid,
  .time-grid {
    grid-template-columns: 1fr;
  }
}
</style>
