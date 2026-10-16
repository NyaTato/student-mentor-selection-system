<script setup lang="ts">
defineProps<{
  label: string
}>()
</script>

<template>
  <div class="nav-group-label">{{ label }}</div>
</template>

<style scoped>
.nav-group-label {
  padding: var(--spacing-sm) var(--spacing-sm) var(--spacing-xxs);
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  letter-spacing: var(--text-eyebrow-spacing);
  color: var(--color-ink-tertiary);
  text-transform: uppercase;
}
</style>
