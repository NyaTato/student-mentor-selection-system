<script setup lang="ts">
defineProps<{
  modelValue: boolean
  disabled?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    :disabled="disabled"
    :class="['toggle', { 'toggle-on': modelValue }, { 'toggle-disabled': disabled }]"
    @click="emit('update:modelValue', !modelValue)"
  >
    <span class="toggle-thumb" />
  </button>
</template>

<style scoped>
.toggle {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: var(--rounded-pill);
  border: none;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s;
  flex-shrink: 0;
}

.toggle-on {
  background: var(--color-primary);
}

.toggle:not(.toggle-on) {
  background: var(--color-hairline-strong);
}

.toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--color-surface-1);
  transition: transform 0.2s;
  box-shadow: var(--shadow-sm);
}

.toggle-on .toggle-thumb {
  transform: translateX(16px);
}

.toggle-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
