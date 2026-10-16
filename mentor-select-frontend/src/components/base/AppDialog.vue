<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'

defineProps<{
  visible: boolean
  title?: string
  width?: number | string
  variant?: 'default' | 'warning' | 'danger'
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

function close() {
  emit('update:visible', false)
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="dialog-overlay" @click="close">
      <div
        class="dialog-content"
        :style="{ '--dialog-width': width ? (typeof width === 'number' ? `${width}px` : width) : undefined } as Record<string, string>"
        @click.stop
      >
        <div v-if="title || $slots.header" class="dialog-header">
          <slot name="header">
            <h2 class="dialog-title" :class="variant && `dialog-title--${variant}`">
              {{ title }}
            </h2>
          </slot>
          <el-button
            class="close-btn"
            :icon="Close"
            circle
            text
            @click="close"
          />
        </div>

        <div class="dialog-body">
          <slot />
        </div>

        <div v-if="$slots.footer" class="dialog-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-semantic-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--spacing-md);
}

.dialog-content {
  background: var(--color-card);
  border-radius: var(--rounded-xl);
  box-shadow: var(--shadow-lg);
  width: var(--dialog-width, 480px);
  max-width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-hairline);
}

.dialog-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
  margin: 0;
}

.dialog-title--warning {
  color: var(--color-semantic-warning);
}

.dialog-title--danger {
  color: var(--color-semantic-error);
}

.close-btn {
  color: var(--color-ink-subtle);
  flex-shrink: 0;
}

.close-btn:hover {
  color: var(--color-ink);
  background: var(--color-surface-3);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-top: var(--spacing-md);
}

@media (max-width: 768px) {
  .dialog-content {
    width: 100vw;
    max-width: 100vw;
    max-height: 100vh;
    border-radius: 0;
  }
}
</style>
