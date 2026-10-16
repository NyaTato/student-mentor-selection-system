<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { SystemState } from '@/types'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import AutoAssignPreview from '@/components/base/AutoAssignPreview.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAutoAssignmentStatusBadge } from '@/utils/badges'

const adminStore = useAdminStore()
const router = useRouter()

/* R10-02 / PROJECT.md 9.5：仅 AUTO_ASSIGN / FINISHED 可执行自动分配 */
const canExecute = computed(
  () =>
    adminStore.systemState === SystemState.AUTO_ASSIGN ||
    adminStore.systemState === SystemState.FINISHED,
)

const isExecuting = ref(false)

/* 执行自动分配 */
async function handleExecute() {
  if (!canExecute.value) return
  if (
    !confirm(
      `确认执行自动分配？\n未匹配学生：${adminStore.autoAssignPreview.totalCandidates} 人\n预计可分配：${adminStore.autoAssignPreview.assignableCount} 人`,
    )
  )
    return
  isExecuting.value = true
  try {
    const result = await adminStore.executeAutoAssign()
    if (!result.success) {
      alert(result.message)
      return
    }
    alert(result.message)
    /* 跳转到结果页查看详情 */
    if (result.logId) {
      router.push(`/admin/auto-assignment-result?logId=${result.logId}`)
    }
  } finally {
    isExecuting.value = false
  }
}

/* 历史批次 */
const historyLogs = computed(() => adminStore.autoAssignmentLogs)

function viewResult(logId: number) {
  router.push(`/admin/auto-assignment-result?logId=${logId}`)
}

const preview = computed(() => adminStore.autoAssignPreview)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">自动分配</h1>
      <p class="page-description">系统按剩余名额自动为未匹配学生分配导师</p>
    </div>

    <!-- 阶段提示 -->
    <StateNotice v-if="!canExecute">
      <StatusBadge variant="warning" label="阶段提示" />
      <span>
        当前系统状态为「{{ adminStore.currentStateLabel }}」，自动分配仅在自动分配阶段或系统结束后可用。
      </span>
    </StateNotice>

    <!-- 并发控制提示 -->
    <StateNotice v-if="adminStore.isAutoAssignRunning">
      <StatusBadge variant="warning" label="运行中" />
      <span>已有自动分配任务正在运行，请等待完成后再执行。</span>
    </StateNotice>

    <!-- 预览 -->
    <section class="section">
      <h2 class="section-title">分配预览</h2>
      <AutoAssignPreview
        :total-candidates="preview.totalCandidates"
        :assignable-count="preview.assignableCount"
        :total-remaining="preview.totalRemaining"
        :is-insufficient="preview.isInsufficient"
        :top-teachers="preview.topTeachers"
        :loading="isExecuting"
        @confirm="handleExecute"
        @cancel="() => {}"
      />
    </section>

    <!-- 历史批次 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">历史批次</h2>
        <span class="section-count">共 {{ historyLogs.length }} 个批次</span>
      </div>
      <AppCard variant="default">
        <div v-if="historyLogs.length" class="log-table">
          <div class="table-header">
            <div class="col-id">批次 ID</div>
            <div class="col-status">状态</div>
            <div class="col-candidates">候选</div>
            <div class="col-assigned">成功</div>
            <div class="col-failed">失败</div>
            <div class="col-time">创建时间</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="log in historyLogs" :key="log.id" class="table-row">
            <div class="col-id">#{{ log.id }}</div>
            <div class="col-status">
              <StatusBadge :variant="getAutoAssignmentStatusBadge(log.status).variant" :label="getAutoAssignmentStatusBadge(log.status).label" />
            </div>
            <div class="col-candidates">{{ log.totalCandidates }}</div>
            <div class="col-assigned">{{ log.assignedCount }}</div>
            <div class="col-failed">{{ log.failedCount }}</div>
            <div class="col-time">{{ formatDateTime(log.createdAt) }}</div>
            <div class="col-action">
              <AppButton variant="tertiary" @click="viewResult(log.id)">查看结果</AppButton>
            </div>
          </div>
        </div>
        <EmptyState v-else title="暂无历史批次" description="执行自动分配后，批次记录将显示在此处" />
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
}

.page-header {
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

.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.section-count {
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
  grid-template-columns: 90px 110px 80px 80px 80px 1.4fr 1fr;
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

.col-assigned {
  color: var(--color-semantic-success);
  font-weight: 500;
}

.col-failed {
  color: var(--color-semantic-error);
  font-weight: 500;
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
  .col-action {
    grid-column: 1 / -1;
  }
}
</style>
