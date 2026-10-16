<script setup lang="ts">
import type { Component } from 'vue'
import { RouterLink } from 'vue-router'

defineProps<{
  to: string
  label: string
  icon?: Component
}>()
</script>

<template>
  <RouterLink :to="to" class="nav-item" active-class="nav-item-active">
    <component :is="icon" v-if="icon" class="nav-icon" />
    <span class="nav-label">{{ label }}</span>
  </RouterLink>
</template>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--rounded-md);
  color: var(--color-ink-muted);
  font-size: var(--text-body-sm);
  transition: background 0.15s, color 0.15s;
}

/* Hover — 浅蓝背景 */
.nav-item:hover {
  background: var(--color-primary-soft);
  color: var(--color-ink);
}

/* Active — 浅蓝背景 + 左侧蓝色高亮条 */
.nav-item-active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-left: 3px solid var(--color-primary);
  font-weight: 500;
}

.nav-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
}
</style>
