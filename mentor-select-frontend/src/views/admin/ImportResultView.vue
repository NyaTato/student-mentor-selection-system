<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import ImportLogDetail from '@/components/base/ImportLogDetail.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getImportTaskStatusBadge, getRoleLabel } from '@/utils/badges'

const route = useRoute()
const router = useRouter()
const adminStore = useAdminStore()

const taskId = computed(() => Number(route.query.taskId))

const task = computed(() =>
  adminStore.importTasks.find((t) => t.id === taskId.value) ?? null,
)

const logs = computed(() =>
  task.value ? adminStore.getImportLogsByTask(task.value.id) : [],
)

/* 重新导入 — 跳回 Excel 导入页 */
function handleReimport() {
  if (!task.value) return
  router.push(`/admin/excel-import?role=${task.value.role}`)
}

function goBack() {
  router.push('/admin/excel-import')
}

/* 统计 */
const stats = computed(() => {
  if (!task.value) return { total: 0, success: 0, fail: 0 }
  return {
    total: task.value.totalRows,
    success: task.value.successCount,
    fail: task.value.failureCount,
  }
})
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <AppButton variant="tertiary" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </AppButton>
      <h1 class="page-title">导入结果详情</h1>
    </div>

    <template v-if="task">
      <!-- 任务摘要 -->
      <section class="section">
        <h2 class="section-title">任务信息</h2>
        <AppCard variant="default">
          <div class="task-summary">
            <div class="summary-row">
              <span class="summary-label">任务 ID</span>
              <span class="summary-value">#{{ task.id }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">导入角色</span>
              <span class="summary-value">{{ getRoleLabel(task.role) }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">文件名</span>
              <span class="summary-value">{{ task.fileName }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">状态</span>
              <StatusBadge :variant="getImportTaskStatusBadge(task.status).variant" :label="getImportTaskStatusBadge(task.status).label" />
            </div>
            <div class="summary-row">
              <span class="summary-label">创建时间</span>
              <span class="summary-value">{{ formatDateTime(task.createdAt) }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-label">完成时间</span>
              <span class="summary-value">{{ formatDateTime(task.completedAt ?? undefined) }}</span>
            </div>
          </div>
        </AppCard>
      </section>

      <!-- 统计 -->
      <section class="section">
        <h2 class="section-title">导入统计</h2>
        <div class="stats-grid">
          <AppCard variant="compact">
            <div class="stat-item">
              <span class="stat-label">总行数</span>
              <span class="stat-value">{{ stats.total }}</span>
            </div>
          </AppCard>
          <AppCard variant="compact">
            <div class="stat-item">
              <span class="stat-label">成功</span>
              <span class="stat-value stat-success">{{ stats.success }}</span>
            </div>
          </AppCard>
          <AppCard variant="compact">
            <div class="stat-item">
              <span class="stat-label">失败</span>
              <span class="stat-value stat-fail">{{ stats.fail }}</span>
            </div>
          </AppCard>
        </div>
      </section>

      <!-- 日志详情 -->
      <section class="section">
        <h2 class="section-title">行日志详情</h2>
        <AppCard variant="default">
          <ImportLogDetail :logs="logs" />
        </AppCard>
      </section>

      <!-- 操作 -->
      <section class="section">
        <div class="actions">
          <AppButton variant="primary" @click="handleReimport">
            重新导入
          </AppButton>
        </div>
      </section>
    </template>

    <AppCard v-else variant="default">
      <EmptyState title="未找到任务" description="该任务不存在或已被删除">
        <AppButton variant="primary" @click="goBack">返回导入页</AppButton>
      </EmptyState>
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.page-title {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.task-summary {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--spacing-sm) var(--spacing-md);
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.summary-value {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-sm);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.stat-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.stat-value {
  font-size: var(--text-display-md);
  font-weight: var(--text-display-md-weight);
  color: var(--color-ink);
}

.stat-success {
  color: var(--color-semantic-success);
}

.stat-fail {
  color: var(--color-semantic-error);
}

.actions {
  display: flex;
  justify-content: flex-end;
}
</style>
