<script setup lang="ts">
import { computed } from 'vue'
import type { StateHistory } from '@/types'
import { StateTransitionType } from '@/types'
import StatusBadge from './StatusBadge.vue'
import EmptyState from './EmptyState.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getStateTransitionTypeBadge } from '@/utils/badges'

const props = defineProps<{
  histories: StateHistory[]
  stateLabels: Record<string, string>
}>()

/* 转换类型对应的左侧颜色条 */
function transitionColor(t: StateTransitionType): string {
  switch (t) {
    case StateTransitionType.MANUAL_FORWARD:
      return 'var(--color-primary)'
    case StateTransitionType.MANUAL_ROLLBACK:
      return 'var(--color-semantic-error)'
    case StateTransitionType.AUTO_SCHEDULED:
      return 'var(--color-semantic-success)'
    default:
      return 'var(--color-ink-subtle)'
  }
}

const hasHistory = computed(() => props.histories.length > 0)
</script>

<template>
  <div class="state-history-timeline">
    <div v-if="hasHistory" class="timeline">
      <div
        v-for="(h, idx) in histories"
        :key="h.id"
        class="timeline-node"
      >
        <!-- 左侧时间线轨道 -->
        <div class="timeline-track">
          <div
            class="timeline-dot"
            :style="{ background: transitionColor(h.transitionType) }"
          />
          <div v-if="idx < histories.length - 1" class="timeline-line" />
        </div>

        <!-- 右侧内容 -->
        <div class="timeline-content">
          <div class="timeline-header">
            <div class="state-transition">
              <span class="state-from">{{ stateLabels[h.fromState] ?? h.fromState }}</span>
              <span class="transition-arrow">→</span>
              <span class="state-to">{{ stateLabels[h.toState] ?? h.toState }}</span>
            </div>
            <StatusBadge
              :variant="getStateTransitionTypeBadge(h.transitionType).variant"
              :label="getStateTransitionTypeBadge(h.transitionType).label"
            />
          </div>
          <div class="timeline-meta">
            <span class="meta-operator">{{ h.operatorName }}</span>
            <span class="meta-time">{{ formatDateTime(h.createdAt) }}</span>
          </div>
          <!-- 回退节点显示原因 -->
          <div v-if="h.reason" class="timeline-reason">
            原因：{{ h.reason }}
          </div>
        </div>
      </div>
    </div>

    <EmptyState v-else title="暂无状态变更记录" description="系统状态变更历史将显示在此处" />
  </div>
</template>

<style scoped>
.state-history-timeline {
  display: flex;
  flex-direction: column;
}

.timeline {
  display: flex;
  flex-direction: column;
}

.timeline-node {
  display: flex;
  gap: var(--spacing-md);
  padding-bottom: var(--spacing-md);
}

.timeline-node:last-child {
  padding-bottom: 0;
}

.timeline-track {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 16px;
}

.timeline-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--color-surface-1);
  box-shadow: 0 0 0 1px var(--color-hairline);
  flex-shrink: 0;
}

.timeline-line {
  flex: 1;
  width: 2px;
  background: var(--color-hairline);
  margin-top: var(--spacing-xs);
}

.timeline-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) 0;
}

.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.state-transition {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--text-body-sm);
}

.state-from {
  color: var(--color-ink-subtle);
}

.transition-arrow {
  color: var(--color-ink-subtle);
  font-weight: 300;
}

.state-to {
  color: var(--color-ink);
  font-weight: 500;
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.meta-operator::before {
  content: '·';
  margin-right: var(--spacing-sm);
  color: var(--color-ink-tertiary);
}

.timeline-reason {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-error-bg);
  border-radius: var(--rounded-sm);
  font-size: var(--text-caption);
  color: var(--color-ink-muted);
  margin-top: var(--spacing-xs);
}
</style>
