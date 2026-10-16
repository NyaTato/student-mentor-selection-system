<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  name: string
  subtitle: string
  icon: Component
}>()
</script>

<template>
  <div class="nav-brand">
    <div class="nav-brand-avatar">
      <component :is="icon" class="nav-brand-icon" />
    </div>
    <div class="nav-brand-name">{{ name }}</div>
    <div class="nav-brand-subtitle">{{ subtitle }}</div>
  </div>
</template>

<style scoped>
.nav-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xxs);
  padding: var(--spacing-md) var(--spacing-sm) var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--color-hairline);
  text-align: center;
}

.nav-brand-avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--rounded-full);
  background: var(--color-primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  margin-bottom: var(--spacing-xxs);
}

.nav-brand-icon {
  width: 24px;
  height: 24px;
}

.nav-brand-name {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
  line-height: 1.2;
  word-break: keep-all;
}

.nav-brand-subtitle {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
  line-height: 1.2;
  word-break: keep-all;
}
</style>
