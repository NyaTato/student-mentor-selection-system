<script setup lang="ts">
defineProps<{
  title: string
  content: string
  createdAt: string
}>()

function formatDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

<template>
  <div class="announcement-card">
    <div class="announcement-indicator" />
    <div class="announcement-header">
      <h3 class="announcement-title">{{ title }}</h3>
      <span class="announcement-time">{{ formatDate(createdAt) }}</span>
    </div>
    <p class="announcement-content">{{ content }}</p>
  </div>
</template>

<style scoped>
.announcement-card {
  position: relative;
  background: var(--color-card);
  border-radius: var(--rounded-lg);
  border: 1px solid var(--color-hairline);
  box-shadow: var(--shadow-card);
  padding: var(--spacing-lg);
  overflow: hidden;
}

.announcement-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--color-primary);
}

.announcement-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.announcement-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.announcement-time {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.announcement-content {
  font-size: var(--text-body-sm);
  line-height: var(--text-body-sm-line);
  color: var(--color-ink-muted);
  white-space: pre-wrap;
}
</style>
