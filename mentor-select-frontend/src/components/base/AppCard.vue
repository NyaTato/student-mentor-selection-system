<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'default' | 'hover' | 'compact'
  }>(),
  {
    variant: 'default',
  },
)
</script>

<template>
  <div :class="['card', `card-${variant}`]">
    <slot />
  </div>
</template>

<style scoped>
.card {
  background: var(--color-card);
  color: var(--color-ink);
  border-radius: var(--rounded-lg);
  border: 1px solid var(--color-hairline);
  box-shadow: var(--shadow-card);
}

.card-default {
  padding: var(--spacing-lg);
}

.card-hover {
  padding: var(--spacing-lg);
  background: var(--color-surface-2);
}

.card-compact {
  padding: var(--spacing-md);
  border-radius: var(--rounded-md);
  box-shadow: var(--shadow-sm);
}
</style>
