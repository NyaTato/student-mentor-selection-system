<script setup lang="ts">
import { computed } from 'vue'
import { useStudentStore } from '@/stores/student'
import { AssignmentSource } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const studentStore = useStudentStore()

/* 当前学生的录取记录 */
const admission = computed(() => studentStore.myAdmission)

/* 录取对应的导师信息 */
const teacher = computed(() => {
  const adm = admission.value
  if (!adm) return undefined
  return studentStore.getTeacherById(adm.teacherId)
})

/* 分配来源展示信息：第一轮录取 / 第二轮匹配 / 管理员人工分配 */
interface SourceDisplay {
  label: string
  variant: 'success' | 'warning' | 'default'
}

const sourceDisplay = computed<SourceDisplay>(() => {
  const source = admission.value?.source
  switch (source) {
    case AssignmentSource.ROUND1:
      return { label: '第一轮录取', variant: 'success' }
    case AssignmentSource.ROUND2:
      return { label: '第二轮匹配', variant: 'success' }
    case AssignmentSource.MANUAL:
      return { label: '管理员人工分配', variant: 'warning' }
    default:
      return { label: '未知', variant: 'default' }
  }
})
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">最终结果</h1>
    <p class="page-description">查看最终导师分配结果</p>

    <!-- 已分配：展示导师信息与分配来源 -->
    <AppCard v-if="admission && teacher" variant="default">
      <!-- 分配来源行 -->
      <div class="status-row">
        <span class="row-label">分配来源</span>
        <StatusBadge
          :label="sourceDisplay.label"
          :variant="sourceDisplay.variant"
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

      <!-- 成功提示 -->
      <div class="alert alert-success">
        导师分配已完成
      </div>
    </AppCard>

    <!-- 未分配：空状态 -->
    <EmptyState
      v-else
      title="等待管理员人工分配"
      description="您尚未被分配导师，请耐心等待管理员完成人工分配"
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

/* 分配来源行 */
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

/* 响应式：窄屏单列 */
@media (max-width: 600px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
