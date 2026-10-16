<script setup lang="ts" generic="T extends string | number">
interface FilterOption {
  label: string
  value: T
}

defineProps<{
  options: FilterOption[]
  modelValue: T
}>()

defineEmits<{
  'update:modelValue': [value: T]
}>()
</script>

<template>
  <div class="filter-options">
    <button
      v-for="opt in options"
      :key="opt.value"
      :class="['filter-btn', { active: modelValue === opt.value }]"
      @click="$emit('update:modelValue', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<style scoped>
.filter-options {
  display: flex;
  gap: var(--spacing-xxs);
  background: var(--color-surface-2);
  padding: 2px;
  border-radius: var(--rounded-md);
}

.filter-btn {
  padding: 4px 12px;
  border: none;
  background: transparent;
  color: var(--color-ink-muted);
  font-size: var(--text-body-sm);
  border-radius: var(--rounded-sm);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.filter-btn:hover {
  color: var(--color-ink);
}

.filter-btn.active {
  background: var(--color-surface-1);
  color: var(--color-ink);
  font-weight: 500;
  box-shadow: var(--shadow-sm);
}
</style>
