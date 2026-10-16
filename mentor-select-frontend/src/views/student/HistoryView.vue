<script setup lang="ts">
import { computed } from 'vue'
import { useStudentStore } from '@/stores/student'
import type { HistoryEntry } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import { formatDateTime } from '@/composables/useFormatTime'

const studentStore = useStudentStore()

/* 三段历史记录，分别 computed */
const round1History = computed<HistoryEntry[]>(() =>
  studentStore.history.filter((h) => h.round === '第一轮'),
)

const round2History = computed<HistoryEntry[]>(() =>
  studentStore.history.filter((h) => h.round === '第二轮'),
)

const finalHistory = computed<HistoryEntry[]>(() =>
  studentStore.history.filter((h) => h.round === '最终分配'),
)

/* 渲染用的段落配置 */
interface HistorySection {
  title: string
  items: HistoryEntry[]
}

const sections = computed<HistorySection[]>(() => [
  { title: '第一轮历史', items: round1History.value },
  { title: '第二轮历史', items: round2History.value },
  { title: '最终分配历史', items: finalHistory.value },
])

/* 状态 → StatusBadge variant 映射 */
type BadgeVariant = 'success' | 'warning' | 'error' | 'default'

function statusVariant(status: string): BadgeVariant {
  if (status.includes('录取') || status.includes('匹配') || status.includes('已分配')) {
    return 'success'
  }
  if (status.includes('待')) {
    return 'warning'
  }
  if (status.includes('未') || status.includes('取消') || status.includes('拒绝')) {
    return 'error'
  }
  return 'default'
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">历史记录</h1>
    <p class="page-description">查看完整申请和分配历史</p>

    <div class="history-list">
      <section
        v-for="section in sections"
        :key="section.title"
        class="history-section"
      >
        <span class="section-eyebrow">{{ section.title }}</span>

        <AppCard variant="default">
          <!-- 有记录：时间线 -->
          <ol v-if="section.items.length" class="timeline">
            <li
              v-for="item in section.items"
              :key="item.id"
              class="timeline-item"
            >
              <span class="timeline-dot" aria-hidden="true"></span>
              <div class="timeline-card">
                <div class="timeline-head">
                  <span class="teacher-name">{{ item.teacherName }}</span>
                  <StatusBadge
                    :label="item.status"
                    :variant="statusVariant(item.status)"
                  />
                </div>
                <div class="timeline-meta">
                  <span class="meta-action">{{ item.action }}</span>
                  <span class="meta-time">{{ formatDateTime(item.timestamp) }}</span>
                </div>
              </div>
            </li>
          </ol>

          <!-- 无记录：占位提示 -->
          <p v-else class="empty-text">暂无记录</p>
        </AppCard>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 720px;
}

.page-title {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
  margin-bottom: var(--spacing-xs);
}

.page-description {
  font-size: var(--text-body);
  color: var(--color-ink-muted);
  margin-bottom: var(--spacing-lg);
}

/* 段落列表 */
.history-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.history-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* eyebrow 标题 */
.section-eyebrow {
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  color: var(--color-ink-subtle);
  letter-spacing: var(--text-eyebrow-spacing);
}

/* 时间线 */
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}

/* 左侧竖线：2px，居中于 8px 圆点（圆点 left:0 宽 8px，中心在 4px → 线 left:3px 宽 2px） */
.timeline::before {
  content: '';
  position: absolute;
  left: 3px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: var(--color-hairline);
}

.timeline-item {
  position: relative;
  padding-left: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
}

.timeline-item:last-child {
  margin-bottom: 0;
}

/* 圆点：8px */
.timeline-dot {
  position: absolute;
  left: 0;
  top: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
}

/* 节点内容卡片 */
.timeline-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.teacher-name {
  font-size: var(--text-body);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.meta-action {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.meta-time {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

/* 空段落提示 */
.empty-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
  margin: 0;
}
</style>
