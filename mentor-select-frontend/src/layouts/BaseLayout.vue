<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStateStore } from '@/stores/systemState'

const systemStateStore = useSystemStateStore()

const stateLabel = computed(() => systemStateStore.label)
</script>

<template>
  <div class="layout">
    <!-- 顶部 Header — 白色半透明 + backdrop blur -->
    <header class="app-header">
      <div class="header-content">
        <div class="header-left">
          <div class="banner-indicator" />
          <span class="banner-text">{{ stateLabel }}</span>
        </div>
        <div class="header-right">
          <slot name="header" />
        </div>
      </div>
    </header>

    <div class="layout-body">
      <!-- 侧边栏 — 白底 -->
      <aside class="sidebar">
        <nav class="sidebar-nav">
          <slot name="sidebar" />
        </nav>
      </aside>

      <!-- 主内容区 — 浅灰背景 -->
      <main class="main-content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Header — 白色半透明 + backdrop blur */
.app-header {
  height: 56px;
  background: var(--color-topbar);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-hairline);
  position: relative;
  z-index: 10;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 var(--spacing-lg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.banner-indicator {
  width: 4px;
  height: 16px;
  border-radius: var(--rounded-xs);
  background: var(--color-primary);
}

.banner-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.layout-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Sidebar — 白底 */
.sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-hairline);
  overflow-y: auto;
}

.sidebar-nav {
  padding: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

/* Main content — 浅灰背景 */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  background: var(--color-canvas);
}
</style>
