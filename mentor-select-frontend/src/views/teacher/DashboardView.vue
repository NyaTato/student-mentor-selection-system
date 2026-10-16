<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTeacherStore } from '@/stores/teacher'
import { useSystemStateStore } from '@/stores/systemState'
import { SystemState, ApplicationStatus } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StatItem from '@/components/base/StatItem.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getApplicationStatusBadge } from '@/utils/badges'

const teacherStore = useTeacherStore()
const systemStateStore = useSystemStateStore()
const router = useRouter()

/* 系统阶段标签 — 复用 systemState store 的单一字典源 */
const phaseLabel = computed(() => systemStateStore.label)
const teacher = computed(() => teacherStore.currentTeacher)
const quota = computed(() => teacherStore.quotaInfo)

/* 仅在导师筛选阶段允许录取/拒绝操作（R2-08） */
const canReview = computed(() => teacherStore.systemState === SystemState.TEACHER_REVIEW)

/* 待审核申请数 */
const pendingApplications = computed(
  () => teacherStore.myApplications.filter((a) => a.status === ApplicationStatus.PENDING).length,
)

/* 最近申请（按时间倒序，前 5 条） */
const recentApplications = computed(() =>
  [...teacherStore.myApplications]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 5),
)

/* 快速操作入口 — 根据系统状态显示 */
interface QuickAction {
  label: string
  path: string
  visible: boolean
}

const quickActions = computed<QuickAction[]>(() => [
  {
    label: '查看申请',
    path: '/teacher/applications',
    visible: teacherStore.systemState === SystemState.TEACHER_REVIEW,
  },
  {
    label: '录取管理',
    path: '/teacher/admission',
    visible: teacherStore.systemState === SystemState.TEACHER_REVIEW,
  },
  {
    label: '已指导学生',
    path: '/teacher/assigned-students',
    visible: teacherStore.systemState === SystemState.FINISHED,
  },
  {
    label: '名额概览',
    path: '/teacher/quota',
    visible: true,
  },
])

const visibleQuickActions = computed(() => quickActions.value.filter((a) => a.visible))

function getStudentName(id: number): string {
  return teacherStore.getStudentById(id)?.name ?? '未知学生'
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">导师首页</h1>
    <p class="page-description">招生概况与待审核申请</p>

    <div class="dashboard">
      <div class="dashboard-main">
        <!-- 当前系统阶段 -->
        <AppCard variant="default">
          <div class="phase-block">
            <span class="phase-eyebrow">当前系统阶段</span>
            <div class="phase-label">{{ phaseLabel }}</div>
            <p v-if="canReview" class="phase-hint">
              当前为导师筛选阶段，请及时审核学生申请
            </p>
          </div>
        </AppCard>

        <!-- 招生概况 -->
        <section class="section">
          <h2 class="section-title">招生概况</h2>
          <div class="quota-grid">
            <AppCard variant="compact">
              <StatItem label="招生名额" :value="quota.max" />
            </AppCard>
            <AppCard variant="compact">
              <StatItem label="已录取" :value="quota.admitted" tone="success" />
            </AppCard>
            <AppCard variant="compact">
              <StatItem
                label="剩余名额"
                :value="quota.remaining"
                :tone="quota.remaining <= 0 ? 'error' : 'default'"
              />
            </AppCard>
            <AppCard variant="compact">
              <StatItem label="待审核申请" :value="pendingApplications" tone="warning" />
            </AppCard>
          </div>
        </section>

        <!-- 导师基础信息 -->
        <section class="section">
          <h2 class="section-title">基础信息</h2>
          <AppCard variant="default">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">姓名</span>
                <span class="info-value">{{ teacher.name }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">职称</span>
                <span class="info-value">{{ teacher.title }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">院系</span>
                <span class="info-value">{{ teacher.department }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">研究方向</span>
                <span class="info-value">{{ teacher.researchArea }}</span>
              </div>
            </div>
          </AppCard>
        </section>

        <!-- 快速操作 -->
        <section v-if="visibleQuickActions.length" class="section">
          <h2 class="section-title">快速操作</h2>
          <div class="quick-actions">
            <AppButton
              v-for="action in visibleQuickActions"
              :key="action.path"
              variant="primary"
              @click="navigate(action.path)"
            >
              {{ action.label }}
            </AppButton>
          </div>
        </section>

        <!-- 最近申请 -->
        <section class="section">
          <div class="section-header">
            <h2 class="section-title">最近申请</h2>
            <AppButton
              v-if="teacherStore.myApplications.length"
              variant="tertiary"
              @click="navigate('/teacher/applications')"
            >
              查看全部
            </AppButton>
          </div>
          <AppCard variant="default">
            <div v-if="recentApplications.length" class="app-list">
              <div v-for="app in recentApplications" :key="app.id" class="app-row">
                <div class="app-info">
                  <span class="app-student">{{ getStudentName(app.studentId) }}</span>
                  <span class="app-time">{{ formatDateTime(app.createdAt) }}</span>
                </div>
                <StatusBadge
                  :variant="getApplicationStatusBadge(app.status).variant"
                  :label="getApplicationStatusBadge(app.status).label"
                />
              </div>
            </div>
            <EmptyState v-else title="暂无学生申请" />
          </AppCard>
        </section>
      </div>

      <!-- 侧栏：名额卡片 -->
      <aside class="dashboard-sidebar">
        <h2 class="section-title">名额信息</h2>
        <AppCard variant="default">
          <div class="quota-block">
            <QuotaBadge :admitted="quota.admitted" :max="quota.max" />
            <p class="quota-hint">
              {{ canReview ? '导师筛选阶段，可修改录取名单' : '当前阶段不可修改录取名单' }}
            </p>
          </div>
        </AppCard>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1100px;
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

.dashboard {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--spacing-lg);
  align-items: start;
}

.dashboard-main {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.dashboard-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

/* 系统阶段 */
.phase-block {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.phase-eyebrow {
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  color: var(--color-ink-subtle);
  letter-spacing: var(--text-eyebrow-spacing);
}

.phase-label {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-primary);
}

.phase-hint {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

/* 名额统计 */
.quota-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-sm);
}

/* 基础信息 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.info-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-value {
  font-size: var(--text-body);
  color: var(--color-ink);
  font-weight: 500;
}

/* 快速操作 */
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

/* 申请列表 */
.app-list {
  display: flex;
  flex-direction: column;
}

.app-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.app-row:last-child {
  border-bottom: none;
}

.app-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.app-student {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.app-time {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

/* 侧栏名额 */
.quota-block {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.quota-hint {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

/* 响应式 */
@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: 1fr;
  }

  .quota-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
