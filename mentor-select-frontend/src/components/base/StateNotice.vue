<script setup lang="ts">
import type { Component } from 'vue'

withDefaults(
  defineProps<{
    variant?: 'warning' | 'success'
    icon?: Component
  }>(),
  {
    variant: 'warning',
    icon: undefined,
  },
)
</script>

<template>
  <div :class="['state-notice', `state-notice-${variant}`]">
    <el-icon v-if="icon" class="notice-icon"><component :is="icon" /></el-icon>
    <slot />
  </div>
</template>

<style scoped>
.state-notice {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  border-radius: var(--rounded-md);
  margin-bottom: var(--spacing-md);
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.state-notice-success {
  background: var(--color-success-bg);
  border-color: var(--color-success-border);
}

.notice-icon {
  flex-shrink: 0;
  font-size: 16px;
}
</style>
