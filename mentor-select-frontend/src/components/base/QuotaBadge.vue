<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  admitted: number
  max: number
}>()

const remainingCount = computed(() => Math.max(0, props.max - props.admitted))
const isFull = computed(() => remainingCount.value <= 0)
</script>

<template>
  <span :class="['quota-badge', isFull ? 'quota-full' : 'quota-available']">
    已录取 {{ admitted }} / 上限 {{ max }}，剩余 {{ remainingCount }}
  </span>
</template>

<style scoped>
.quota-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--rounded-pill);
  font-size: var(--text-caption);
  line-height: var(--text-caption-line);
  white-space: nowrap;
}

.quota-available {
  background: var(--color-success-bg);
  color: var(--color-semantic-success);
  border: 1px solid var(--color-success-border);
}

.quota-full {
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
  border: 1px solid var(--color-error-border);
}
</style>
