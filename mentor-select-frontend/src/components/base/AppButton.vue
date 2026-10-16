<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'tertiary' | 'danger'
    disabled?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  {
    variant: 'primary',
    disabled: false,
    type: 'button',
  },
)
</script>

<template>
  <button :type="type" :disabled="disabled" :class="['btn', `btn-${variant}`, { 'btn-disabled': disabled }]">
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) 14px;
  border-radius: var(--rounded-md);
  border: none;
  font-size: var(--text-button);
  font-weight: var(--text-button-weight);
  line-height: var(--text-button-line);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  white-space: nowrap;
}

/* Primary — 蓝色 */
.btn-primary {
  background: var(--color-primary);
  color: var(--color-surface-1);
}
.btn-primary:hover {
  background: var(--color-primary-hover);
}
.btn-primary:active {
  background: var(--color-primary-hover);
}

/* Secondary — 白底描边 */
.btn-secondary {
  background: var(--color-surface-1);
  color: var(--color-ink);
  border: 1px solid var(--color-hairline);
}
.btn-secondary:hover {
  background: var(--color-surface-2);
}

/* Tertiary / Ghost — 透明 */
.btn-tertiary {
  background: transparent;
  color: var(--color-ink);
}
.btn-tertiary:hover {
  background: var(--color-surface-2);
}

/* Danger — 红色 */
.btn-danger {
  background: var(--color-semantic-error);
  color: var(--color-surface-1);
}
.btn-danger:hover {
  background: var(--color-semantic-error);
  opacity: 0.9;
}

/* Disabled — 对应 DESIGN.md button-disabled */
.btn-disabled {
  background: var(--color-surface-3) !important;
  color: var(--color-ink-tertiary) !important;
  border: 1px solid var(--color-hairline) !important;
  cursor: not-allowed;
  opacity: 1;
}
.btn-disabled:hover {
  background: var(--color-surface-3) !important;
  opacity: 1;
}
</style>
