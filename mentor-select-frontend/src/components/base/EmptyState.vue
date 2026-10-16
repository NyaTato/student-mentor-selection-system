<script setup lang="ts">
import { Files } from '@element-plus/icons-vue'

defineProps<{
  title?: string
  description?: string
}>()
</script>

<template>
  <div class="empty-state">
    <div class="empty-icon"><el-icon :size="48"><Files /></el-icon></div>
    <p v-if="title" class="empty-title">{{ title }}</p>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xxl);
  text-align: center;
}

.empty-icon {
  color: var(--color-ink-tertiary);
  margin-bottom: var(--spacing-md);
}

.empty-title {
  font-size: var(--text-body);
  color: var(--color-ink-subtle);
  margin-bottom: var(--spacing-xs);
}

.empty-description {
  font-size: var(--text-body-sm);
  color: var(--color-ink-tertiary);
}
</style>
