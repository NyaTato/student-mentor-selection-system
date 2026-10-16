<script setup lang="ts">
import { computed } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { Reading, UserFilled, Document, CircleCheck, Clock, Link } from '@element-plus/icons-vue'
import { formatTimeShort } from '@/composables/useFormatTime'

const adminStore = useAdminStore()

/* 系统状态 */
const stateLabel = computed(() => adminStore.currentStateLabel)
const stats = computed(() => adminStore.stats)

/* 各阶段申请统计 */
const applicationStats = computed(() => {
  const apps = adminStore.applications
  return {
    total: apps.length,
    pending: apps.filter((a) => a.status === 'PENDING').length,
    accepted: apps.filter((a) => a.status === 'ACCEPTED').length,
    rejected: apps.filter((a) => a.status === 'REJECTED').length,
  }
})

/* 录取率 */
const admissionRate = computed(() => {
  if (stats.value.studentCount === 0) return 0
  return Math.round((stats.value.admissionCount / stats.value.studentCount) * 100)
})

/* 未匹配率 */
const unmatchedRate = computed(() => {
  if (stats.value.studentCount === 0) return 0
  return Math.round((stats.value.unmatchedStudentCount / stats.value.studentCount) * 100)
})

/* 导师名额使用率 */
const teacherUsage = computed(() =>
  adminStore.teachers
    .map((t) => ({
      name: t.name,
      department: t.department,
      admitted: t.currentAdmitted,
      max: t.maxQuota,
      rate: t.maxQuota === 0 ? 0 : Math.round((t.currentAdmitted / t.maxQuota) * 100),
    }))
    .sort((a, b) => b.rate - a.rate),
)

/* 最近日志 */
const recentLogs = computed(() => adminStore.logs.slice(0, 8))

/* Stripe KPI 卡片数据 — accent 映射到 Stripe 图表色板 */
const statCards = computed(() => [
  { label: '学生总数', value: stats.value.studentCount, icon: Reading, accent: 'primary' },
  { label: '导师总数', value: stats.value.teacherCount, icon: UserFilled, accent: 'shadow-blue' },
  { label: '申请总数', value: stats.value.applicationCount, icon: Document, accent: 'lemon' },
  { label: '已录取', value: stats.value.admissionCount, icon: CircleCheck, accent: 'primary' },
  { label: '待审核申请', value: stats.value.pendingApplicationCount, icon: Clock, accent: 'lemon' },
  { label: '未匹配学生', value: stats.value.unmatchedStudentCount, icon: Link, accent: 'ruby' },
])
</script>

<template>
  <div class="stripe-dashboard">
    <div class="dashboard-header">
      <div>
        <h1 class="page-title">统计分析</h1>
        <p class="page-description">系统数据统计与分析</p>
      </div>
      <div class="state-indicator">
        <span class="state-label">当前状态</span>
        <span class="state-pill">{{ stateLabel }}</span>
      </div>
    </div>

    <!-- Stripe KPI 卡片 -->
    <section class="stat-grid">
      <div v-for="card in statCards" :key="card.label" :class="['kpi-card', `kpi-${card.accent}`]">
        <div class="kpi-card-content">
          <div class="kpi-card-icon"><el-icon><component :is="card.icon" /></el-icon></div>
          <div class="kpi-card-info">
            <span class="kpi-card-label">{{ card.label }}</span>
            <span class="kpi-card-value">{{ card.value }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 录取概览 -->
    <section class="section">
      <h2 class="section-title">录取概览</h2>
      <div class="overview-grid">
        <div class="chart-card">
          <div class="overview-item">
            <span class="overview-label">录取率</span>
            <div class="overview-value-row">
              <span class="overview-value">{{ admissionRate }}%</span>
              <div class="progress-bar">
                <div class="progress-fill progress-fill-primary" :style="{ width: `${admissionRate}%` }" />
              </div>
            </div>
          </div>
        </div>
        <div class="chart-card">
          <div class="overview-item">
            <span class="overview-label">未匹配率</span>
            <div class="overview-value-row">
              <span class="overview-value">{{ unmatchedRate }}%</span>
              <div class="progress-bar">
                <div class="progress-fill progress-fill-ruby" :style="{ width: `${unmatchedRate}%` }" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 申请状态分布 -->
    <section class="section">
      <h2 class="section-title">申请状态分布</h2>
      <div class="chart-card">
        <div class="status-distribution">
          <div class="status-bar">
            <div class="status-bar-pending" :style="{ width: `${(applicationStats.pending / Math.max(1, applicationStats.total)) * 100}%` }" />
            <div class="status-bar-accepted" :style="{ width: `${(applicationStats.accepted / Math.max(1, applicationStats.total)) * 100}%` }" />
            <div class="status-bar-rejected" :style="{ width: `${(applicationStats.rejected / Math.max(1, applicationStats.total)) * 100}%` }" />
          </div>
          <div class="status-legend">
            <div class="legend-item">
              <span class="legend-dot legend-pending" />
              <span class="legend-label">待审核</span>
              <span class="legend-value">{{ applicationStats.pending }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot legend-accepted" />
              <span class="legend-label">已录取</span>
              <span class="legend-value">{{ applicationStats.accepted }}</span>
            </div>
            <div class="legend-item">
              <span class="legend-dot legend-rejected" />
              <span class="legend-label">已拒绝</span>
              <span class="legend-value">{{ applicationStats.rejected }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="bottom-grid">
      <!-- 导师名额使用率 -->
      <section class="section">
        <h2 class="section-title">导师名额使用率</h2>
        <div class="chart-card">
          <div class="teacher-usage-list">
            <div v-for="t in teacherUsage" :key="t.name" class="teacher-usage-row">
              <div class="teacher-info">
                <span class="teacher-name">{{ t.name }}</span>
                <span class="teacher-meta">{{ t.department }} · {{ t.admitted }}/{{ t.max }}</span>
              </div>
              <div class="usage-bar">
                <div class="usage-fill" :style="{ width: `${t.rate}%` }" />
              </div>
              <span class="usage-rate">{{ t.rate }}%</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 最近日志 -->
      <section class="section">
        <h2 class="section-title">最近操作</h2>
        <div class="chart-card">
          <div class="log-list">
            <div v-for="log in recentLogs" :key="log.id" class="log-row">
              <div class="log-info">
                <span class="log-action">{{ log.action }}</span>
                <span v-if="log.target" class="log-target">{{ log.target }}</span>
              </div>
              <span class="log-time">{{ formatTimeShort(log.timestamp) }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ========== Stripe Design Language — 仅限管理员统计分析页面 ==========
 * 对应 DESIGN.md 第二部分
 * 所有 token 使用 --stripe-* 前缀，不混用 Linear 的 --color-* / --text-* / --spacing-* / --rounded-*
 * Display 使用 weight 300；所有数字使用 tabular-nums (DESIGN.md §2.2 / §2.7)
 */
.stripe-dashboard {
  max-width: 1200px;
  font-family: var(--stripe-font-display);
  color: var(--stripe-color-ink);
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--stripe-spacing-xl);
}

.page-title {
  font-size: var(--stripe-text-display-xl);
  font-weight: var(--stripe-text-display-xl-weight);
  line-height: var(--stripe-text-display-xl-line);
  letter-spacing: var(--stripe-text-display-xl-spacing);
  color: var(--stripe-color-ink);
  margin-bottom: var(--stripe-spacing-xs);
}

.page-description {
  font-size: var(--stripe-text-body-lg);
  font-weight: var(--stripe-text-body-lg-weight);
  color: var(--stripe-color-ink-mute);
}

.state-indicator {
  display: flex;
  align-items: center;
  gap: var(--stripe-spacing-sm);
}

.state-label {
  font-size: var(--stripe-text-caption);
  color: var(--stripe-color-ink-mute);
}

.state-pill {
  padding: var(--stripe-spacing-xs) var(--stripe-spacing-md);
  border-radius: var(--stripe-rounded-pill);
  background: var(--stripe-color-brand-dark-900);
  color: var(--stripe-color-canvas);
  font-size: var(--stripe-text-caption);
  font-weight: var(--stripe-text-caption-weight);
}

/* ========== KPI 卡片 — DESIGN.md §2.5 kpi-card ========== */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--stripe-spacing-lg);
  margin-bottom: var(--stripe-spacing-xl);
}

.kpi-card {
  position: relative;
  overflow: hidden;
  background: var(--stripe-color-canvas);
  border: 1px solid var(--stripe-color-hairline);
  border-radius: var(--stripe-rounded-lg);
  padding: var(--stripe-spacing-xxl);
  /* Level 1 阴影 — DESIGN.md §2.6 */
  box-shadow: var(--shadow-sm);
}

.kpi-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.kpi-primary::before { background: var(--stripe-color-primary); }
.kpi-shadow-blue::before { background: var(--stripe-color-shadow-blue); }
.kpi-lemon::before { background: var(--stripe-color-lemon); }
.kpi-ruby::before { background: var(--stripe-color-ruby); }

.kpi-card-content {
  display: flex;
  align-items: center;
  gap: var(--stripe-spacing-lg);
}

.kpi-card-icon {
  font-size: 32px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--stripe-color-canvas-soft);
  border-radius: var(--stripe-rounded-md);
}

.kpi-card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-card-label {
  font-size: var(--stripe-text-caption);
  color: var(--stripe-color-ink-mute);
}

.kpi-card-value {
  font-size: var(--stripe-text-display-lg);
  font-weight: var(--stripe-text-display-lg-weight);
  line-height: var(--stripe-text-display-lg-line);
  letter-spacing: var(--stripe-text-display-lg-spacing);
  color: var(--stripe-color-ink);
  font-variant-numeric: tabular-nums;
}

/* ========== Section ========== */
.section {
  margin-bottom: var(--stripe-spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--stripe-spacing-sm);
}

.section-title {
  font-size: var(--stripe-text-heading-lg);
  font-weight: var(--stripe-text-heading-lg-weight);
  line-height: var(--stripe-text-heading-lg-line);
  letter-spacing: var(--stripe-text-heading-lg-spacing);
  color: var(--stripe-color-ink);
}

/* ========== Chart 卡片 — DESIGN.md §2.5 chart-card ========== */
.chart-card {
  background: var(--stripe-color-canvas);
  border: 1px solid var(--stripe-color-hairline);
  border-radius: var(--stripe-rounded-lg);
  padding: var(--stripe-spacing-xl);
  /* Level 2 阴影 — DESIGN.md §2.6 */
  box-shadow: var(--shadow-lg);
}

/* ========== 录取概览 ========== */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--stripe-spacing-lg);
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: var(--stripe-spacing-sm);
}

.overview-label {
  font-size: var(--stripe-text-body-md);
  color: var(--stripe-color-ink-mute);
}

.overview-value-row {
  display: flex;
  align-items: center;
  gap: var(--stripe-spacing-lg);
}

.overview-value {
  font-size: var(--stripe-text-display-md);
  font-weight: var(--stripe-text-display-md-weight);
  line-height: var(--stripe-text-display-md-line);
  letter-spacing: var(--stripe-text-display-md-spacing);
  color: var(--stripe-color-ink);
  min-width: 60px;
  font-variant-numeric: tabular-nums;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--stripe-color-canvas-soft);
  border-radius: var(--stripe-rounded-pill);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--stripe-rounded-pill);
  transition: width 0.3s ease;
}

.progress-fill-primary { background: var(--stripe-color-primary); }
.progress-fill-ruby { background: var(--stripe-color-ruby); }

/* ========== 申请状态分布 ========== */
.status-distribution {
  display: flex;
  flex-direction: column;
  gap: var(--stripe-spacing-lg);
}

.status-bar {
  display: flex;
  width: 100%;
  height: 12px;
  border-radius: var(--stripe-rounded-pill);
  overflow: hidden;
  background: var(--stripe-color-canvas-soft);
}

.status-bar-pending { background: var(--stripe-color-lemon); }
.status-bar-accepted { background: var(--stripe-color-primary); }
.status-bar-rejected { background: var(--stripe-color-ruby); }

.status-legend {
  display: flex;
  gap: var(--stripe-spacing-xl);
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--stripe-spacing-xs);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-pending { background: var(--stripe-color-lemon); }
.legend-accepted { background: var(--stripe-color-primary); }
.legend-rejected { background: var(--stripe-color-ruby); }

.legend-label {
  font-size: var(--stripe-text-body-md);
  color: var(--stripe-color-ink-secondary);
}

.legend-value {
  font-size: var(--stripe-text-body-tabular);
  font-weight: var(--stripe-text-body-tabular-weight);
  color: var(--stripe-color-ink);
  font-variant-numeric: tabular-nums;
}

/* ========== 底部双列 ========== */
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--stripe-spacing-xl);
}

/* 导师名额使用率 */
.teacher-usage-list {
  display: flex;
  flex-direction: column;
  gap: var(--stripe-spacing-sm);
}

.teacher-usage-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: var(--stripe-spacing-sm);
  align-items: center;
}

.teacher-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-name {
  font-size: var(--stripe-text-body-md);
  font-weight: 500;
  color: var(--stripe-color-ink);
}

.teacher-meta {
  font-size: var(--stripe-text-caption);
  color: var(--stripe-color-ink-mute);
  font-variant-numeric: tabular-nums;
}

.usage-bar {
  height: 6px;
  background: var(--stripe-color-canvas-soft);
  border-radius: var(--stripe-rounded-pill);
  overflow: hidden;
}

.usage-fill {
  height: 100%;
  background: var(--stripe-color-primary);
  border-radius: var(--stripe-rounded-pill);
}

.usage-rate {
  font-size: var(--stripe-text-body-tabular);
  font-weight: 500;
  color: var(--stripe-color-ink);
  min-width: 40px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 日志列表 */
.log-list {
  display: flex;
  flex-direction: column;
}

.log-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--stripe-spacing-xs) 0;
  border-bottom: 1px solid var(--stripe-color-hairline);
  gap: var(--stripe-spacing-sm);
}

.log-row:last-child { border-bottom: none; }

.log-info {
  display: flex;
  align-items: center;
  gap: var(--stripe-spacing-xs);
  min-width: 0;
}

.log-action {
  font-size: var(--stripe-text-body-md);
  color: var(--stripe-color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-target {
  font-size: var(--stripe-text-caption);
  color: var(--stripe-color-ink-mute);
}

.log-time {
  font-size: var(--stripe-text-caption);
  color: var(--stripe-color-ink-mute);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* 响应式 */
@media (max-width: 900px) {
  .stat-grid { grid-template-columns: repeat(2, 1fr); }
  .overview-grid { grid-template-columns: 1fr; }
  .bottom-grid { grid-template-columns: 1fr; }
}
</style>
