<script lang="ts">
/* 统计数值的语义色调 — 与 BadgeVariant 不同：StatItem 用于统计数值展示，额外包含 info（蓝色信息色调） */
export type StatTone = 'default' | 'success' | 'warning' | 'error' | 'info'
</script>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    tone?: StatTone
  }>(),
  {
    tone: 'default',
  },
)
</script>

<template>
  <div class="stat-item">
    <span class="stat-label">{{ label }}</span>
    <span :class="['stat-value', `stat-value-${tone}`]">{{ value }}</span>
  </div>
</template>

<style scoped>
.stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.stat-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.stat-value {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

.stat-value-success {
  color: var(--color-semantic-success);
}

.stat-value-warning {
  color: var(--color-semantic-warning);
}

.stat-value-error {
  color: var(--color-semantic-error);
}

.stat-value-info {
  color: var(--color-primary);
}
</style>
