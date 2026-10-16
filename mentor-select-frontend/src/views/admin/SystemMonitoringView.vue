<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import { formatTimeWithSeconds } from '@/composables/useFormatTime'

const adminStore = useAdminStore()

/* 模拟实时监控数据 */
const currentTime = ref(new Date())

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timer = setInterval(() => {
    currentTime.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

/* 系统运行状态指标（Mock） */
const metrics = computed(() => ({
  uptime: '15 天 4 小时',
  cpuUsage: Math.floor(20 + Math.random() * 30),
  memoryUsage: Math.floor(40 + Math.random() * 20),
  diskUsage: 35,
  activeUsers: Math.floor(5 + Math.random() * 20),
  requestPerMinute: Math.floor(50 + Math.random() * 100),
}))

/* 服务状态 */
const services = computed(() => [
  { name: 'Web 服务', status: 'running', uptime: '99.9%' },
  { name: 'API 服务', status: 'running', uptime: '99.95%' },
  { name: '数据库服务', status: 'running', uptime: '100%' },
  { name: 'Redis 缓存', status: 'running', uptime: '99.8%' },
  { name: '消息队列', status: 'running', uptime: '99.9%' },
])

function getServiceBadge(status: string) {
  switch (status) {
    case 'running':
      return { variant: 'success' as const, label: '运行中' }
    case 'stopped':
      return { variant: 'error' as const, label: '已停止' }
    case 'warning':
      return { variant: 'warning' as const, label: '异常' }
    default:
      return { variant: 'default' as const, label: '未知' }
  }
}

/* 进度条宽度 */
function getBarWidth(value: number): string {
  return `${Math.min(100, value)}%`
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统监控</h1>
        <p class="page-description">系统运行状态监控</p>
      </div>
      <div class="time-display">
        <span class="time-label">当前时间</span>
        <span class="time-value">{{ formatTimeWithSeconds(currentTime) }}</span>
      </div>
    </div>

    <!-- 系统概览 -->
    <section class="section">
      <h2 class="section-title">系统概览</h2>
      <div class="overview-grid">
        <AppCard variant="default">
          <div class="metric-item">
            <span class="metric-label">系统运行时长</span>
            <span class="metric-value">{{ metrics.uptime }}</span>
          </div>
        </AppCard>
        <AppCard variant="default">
          <div class="metric-item">
            <span class="metric-label">活跃用户数</span>
            <span class="metric-value">{{ metrics.activeUsers }}</span>
          </div>
        </AppCard>
        <AppCard variant="default">
          <div class="metric-item">
            <span class="metric-label">每分钟请求数</span>
            <span class="metric-value">{{ metrics.requestPerMinute }}</span>
          </div>
        </AppCard>
        <AppCard variant="default">
          <div class="metric-item">
            <span class="metric-label">系统状态</span>
            <StatusBadge variant="success" label="正常运行" />
          </div>
        </AppCard>
      </div>
    </section>

    <!-- 资源使用率 -->
    <section class="section">
      <h2 class="section-title">资源使用率</h2>
      <AppCard variant="default">
        <div class="resource-list">
          <div class="resource-row">
            <div class="resource-info">
              <span class="resource-name">CPU 使用率</span>
              <span class="resource-value" :class="{ 'resource-warning': metrics.cpuUsage > 70 }">
                {{ metrics.cpuUsage }}%
              </span>
            </div>
            <div class="resource-bar">
              <div
                class="resource-fill"
                :class="{ 'fill-warning': metrics.cpuUsage > 70 }"
                :style="{ width: getBarWidth(metrics.cpuUsage) }"
              />
            </div>
          </div>
          <div class="resource-row">
            <div class="resource-info">
              <span class="resource-name">内存使用率</span>
              <span class="resource-value" :class="{ 'resource-warning': metrics.memoryUsage > 80 }">
                {{ metrics.memoryUsage }}%
              </span>
            </div>
            <div class="resource-bar">
              <div
                class="resource-fill"
                :class="{ 'fill-warning': metrics.memoryUsage > 80 }"
                :style="{ width: getBarWidth(metrics.memoryUsage) }"
              />
            </div>
          </div>
          <div class="resource-row">
            <div class="resource-info">
              <span class="resource-name">磁盘使用率</span>
              <span class="resource-value">{{ metrics.diskUsage }}%</span>
            </div>
            <div class="resource-bar">
              <div class="resource-fill" :style="{ width: getBarWidth(metrics.diskUsage) }" />
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 服务状态 -->
    <section class="section">
      <h2 class="section-title">服务状态</h2>
      <AppCard variant="default">
        <div class="service-table">
          <div class="service-table-header">
            <div class="col-name">服务名称</div>
            <div class="col-status">状态</div>
            <div class="col-uptime">可用率</div>
          </div>
          <div v-for="svc in services" :key="svc.name" class="service-table-row">
            <div class="col-name">{{ svc.name }}</div>
            <div class="col-status">
              <StatusBadge
                :variant="getServiceBadge(svc.status).variant"
                :label="getServiceBadge(svc.status).label"
              />
            </div>
            <div class="col-uptime">{{ svc.uptime }}</div>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 当前系统状态 -->
    <section class="section">
      <h2 class="section-title">业务状态</h2>
      <AppCard variant="default">
        <div class="business-info">
          <div class="info-item">
            <span class="info-label">当前业务阶段</span>
            <StatusBadge variant="success" :label="adminStore.currentStateLabel" />
          </div>
          <div class="info-item">
            <span class="info-label">学生总数</span>
            <span class="info-value">{{ adminStore.stats.studentCount }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">导师总数</span>
            <span class="info-value">{{ adminStore.stats.teacherCount }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">申请总数</span>
            <span class="info-value">{{ adminStore.stats.applicationCount }}</span>
          </div>
        </div>
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
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
}

.time-display {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.time-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.time-value {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

/* Section */
.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

/* 概览 */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.metric-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.metric-value {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

/* 资源使用率 */
.resource-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.resource-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.resource-name {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.resource-value {
  font-size: var(--text-body);
  font-weight: 600;
  color: var(--color-semantic-success);
}

.resource-warning {
  color: var(--color-semantic-warning);
}

.resource-bar {
  height: 8px;
  background: var(--color-surface-3);
  border-radius: var(--rounded-pill);
  overflow: hidden;
}

.resource-fill {
  height: 100%;
  background: var(--color-semantic-success);
  border-radius: var(--rounded-pill);
  transition: width 0.3s ease;
}

.fill-warning {
  background: var(--color-semantic-warning);
}

/* 服务状态表 */
.service-table {
  display: flex;
  flex-direction: column;
}

.service-table-header,
.service-table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.service-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.service-table-row {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.service-table-row:last-child { border-bottom: none; }

.col-name {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.col-uptime {
  font-size: var(--text-body-sm);
  color: var(--color-semantic-success);
  font-weight: 600;
}

/* 业务状态 */
.business-info {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.info-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-value {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

@media (max-width: 900px) {
  .overview-grid { grid-template-columns: repeat(2, 1fr); }
  .business-info { grid-template-columns: repeat(2, 1fr); }
}
</style>
