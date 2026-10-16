<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { View } from '@element-plus/icons-vue'
import type { ImportTask } from '@/types'
import AppButton from './AppButton.vue'
import StatusBadge from './StatusBadge.vue'
import EmptyState from './EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getImportTaskStatusBadge, getRoleLabel } from '@/utils/badges'

const props = defineProps<{
  tasks: ImportTask[]
}>()

const router = useRouter()

function viewDetail(taskId: number) {
  router.push(`/admin/import-result?taskId=${taskId}`)
}

const hasTasks = computed(() => props.tasks.length > 0)
</script>

<template>
  <div class="import-task-list">
    <div v-if="hasTasks" class="task-table">
      <div class="table-header">
        <div class="col-id">任务 ID</div>
        <div class="col-role">角色</div>
        <div class="col-file">文件名</div>
        <div class="col-status">状态</div>
        <div class="col-success">成功</div>
        <div class="col-fail">失败</div>
        <div class="col-time">创建时间</div>
        <div class="col-action">操作</div>
      </div>
      <div v-for="t in tasks" :key="t.id" class="table-row">
        <div class="col-id">{{ t.id }}</div>
        <div class="col-role">{{ getRoleLabel(t.role) }}</div>
        <div class="col-file" :title="t.fileName">{{ t.fileName }}</div>
        <div class="col-status">
          <StatusBadge :variant="getImportTaskStatusBadge(t.status).variant" :label="getImportTaskStatusBadge(t.status).label" />
        </div>
        <div class="col-success">{{ t.successCount }}</div>
        <div class="col-fail">{{ t.failureCount }}</div>
        <div class="col-time">{{ formatDateTime(t.createdAt) }}</div>
        <div class="col-action">
          <AppButton variant="tertiary" @click="viewDetail(t.id)">
            <el-icon><View /></el-icon>
            查看详情
          </AppButton>
        </div>
      </div>
    </div>
    <EmptyState v-else title="暂无导入任务" description="完成 Excel 导入后，任务记录将显示在此处" />
  </div>
</template>

<style scoped>
.task-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 80px 80px 1.6fr 110px 70px 70px 1.4fr 1fr;
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

.col-file {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-success {
  color: var(--color-semantic-success);
  font-weight: 500;
}

.col-fail {
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
