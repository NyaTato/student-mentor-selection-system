<script setup lang="ts">
import { computed } from 'vue'
import { useTeacherStore } from '@/stores/teacher'
import { ApplicationStatus } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'

const teacherStore = useTeacherStore()

const teacher = computed(() => teacherStore.currentTeacher)
const quota = computed(() => teacherStore.quotaInfo)

/* 申请统计 */
const applicationStats = computed(() => {
  const apps = teacherStore.myApplications
  return {
    total: apps.length,
    pending: apps.filter((a) => a.status === ApplicationStatus.PENDING).length,
    accepted: apps.filter((a) => a.status === ApplicationStatus.ACCEPTED).length,
    rejected: apps.filter((a) => a.status === ApplicationStatus.REJECTED).length,
  }
})

/* 录取统计 */
const admissionStats = computed(() => {
  const adms = teacherStore.myAdmissions
  return {
    total: adms.length,
    round1: adms.filter((a) => a.source === '第一轮录取').length,
    round2: adms.filter((a) => a.source === '第二轮匹配').length,
    manual: adms.filter((a) => a.source === '管理员人工分配').length,
  }
})

/* 名额使用率 */
const usageRate = computed(() => {
  if (quota.value.max === 0) return 0
  return Math.round((quota.value.admitted / quota.value.max) * 100)
})

/* 进度条宽度 */
const progressBarWidth = computed(() => `${Math.min(100, usageRate.value)}%`)
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">名额概览</h1>
    <p class="page-description">招生名额与申请情况统计</p>

    <!-- 名额总览 -->
    <AppCard variant="default">
      <div class="quota-header">
        <div class="quota-title">
          <span class="quota-name">{{ teacher.name }}</span>
          <span class="quota-meta">{{ teacher.department }} · {{ teacher.title }}</span>
        </div>
        <QuotaBadge :admitted="quota.admitted" :max="quota.max" />
      </div>
      <div class="quota-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressBarWidth }" />
        </div>
        <div class="progress-text">名额使用率 {{ usageRate }}%</div>
      </div>
      <div class="quota-stats">
        <div class="stat-item">
          <span class="stat-label">招生名额</span>
          <span class="stat-value">{{ quota.max }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">已录取</span>
          <span class="stat-value stat-value-success">{{ quota.admitted }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">剩余</span>
          <span class="stat-value" :class="{ 'stat-value-error': quota.remaining <= 0 }">
            {{ quota.remaining }}
          </span>
        </div>
      </div>
    </AppCard>

    <!-- 申请统计 -->
    <section class="section">
      <h2 class="section-title">申请统计</h2>
      <div class="stats-grid">
        <AppCard variant="compact">
          <div class="stat-card">
            <span class="stat-card-label">申请总数</span>
            <span class="stat-card-value">{{ applicationStats.total }}</span>
          </div>
        </AppCard>
        <AppCard variant="compact">
          <div class="stat-card">
            <span class="stat-card-label">待审核</span>
            <span class="stat-card-value stat-value-warning">{{ applicationStats.pending }}</span>
          </div>
        </AppCard>
        <AppCard variant="compact">
          <div class="stat-card">
            <span class="stat-card-label">已录取</span>
            <span class="stat-card-value stat-value-success">{{ applicationStats.accepted }}</span>
          </div>
        </AppCard>
        <AppCard variant="compact">
          <div class="stat-card">
            <span class="stat-card-label">已拒绝</span>
            <span class="stat-card-value stat-value-error">{{ applicationStats.rejected }}</span>
          </div>
        </AppCard>
      </div>
    </section>

    <!-- 录取来源统计 -->
    <section class="section">
      <h2 class="section-title">录取来源分布</h2>
      <AppCard variant="default">
        <div class="source-list">
          <div class="source-row">
            <span class="source-label">第一轮录取</span>
            <span class="source-value">{{ admissionStats.round1 }}</span>
          </div>
          <div class="source-row">
            <span class="source-label">第二轮匹配</span>
            <span class="source-value">{{ admissionStats.round2 }}</span>
          </div>
          <div class="source-row">
            <span class="source-label">管理员人工分配</span>
            <span class="source-value">{{ admissionStats.manual }}</span>
          </div>
          <div class="source-row source-row-total">
            <span class="source-label">合计</span>
            <span class="source-value">{{ admissionStats.total }}</span>
          </div>
        </div>
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
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

/* 名额总览 */
.quota-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.quota-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quota-name {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.quota-meta {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

.quota-progress {
  margin-bottom: var(--spacing-md);
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--color-surface-3);
  border-radius: var(--rounded-pill);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--rounded-pill);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
  margin-top: var(--spacing-xs);
}

.quota-stats {
  display: flex;
  gap: var(--spacing-xl);
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.stat-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.stat-value {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

.stat-value-success {
  color: var(--color-semantic-success);
}

.stat-value-warning {
  color: var(--color-semantic-warning);
}

.stat-value-error {
  color: var(--color-semantic-error);
}

/* 统计网格 */
.section {
  margin-top: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.stat-card-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.stat-card-value {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

/* 录取来源 */
.source-list {
  display: flex;
  flex-direction: column;
}

.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.source-row:last-child {
  border-bottom: none;
}

.source-row-total {
  margin-top: var(--spacing-xs);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  border-bottom: none;
  font-weight: 600;
}

.source-label {
  font-size: var(--text-body);
  color: var(--color-ink-muted);
}

.source-row-total .source-label {
  color: var(--color-ink);
}

.source-value {
  font-size: var(--text-body);
  font-weight: 600;
  color: var(--color-ink);
}

@media (max-width: 900px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
