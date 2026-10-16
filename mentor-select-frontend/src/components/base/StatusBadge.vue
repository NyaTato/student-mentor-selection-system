<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'success' | 'warning' | 'error' | 'default'
    label: string
  }>(),
  {
    variant: 'default',
  },
)
</script>

<template>
  <span :class="['status-badge', `status-badge-${variant}`]">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--spacing-xs);
  border-radius: var(--rounded-pill);
  font-size: var(--text-caption);
  line-height: var(--text-caption-line);
  font-weight: 500;
  white-space: nowrap;
}

.status-badge-default {
  background: var(--color-surface-3);
  color: var(--color-ink-muted);
}

.status-badge-success {
  background: var(--color-success-bg);
  color: var(--color-semantic-success);
}

.status-badge-warning {
  background: var(--color-warning-bg);
  color: var(--color-semantic-warning);
}

.status-badge-error {
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
}
</style>
