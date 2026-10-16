<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import { useSystemStateStore } from '@/stores/systemState'
import { SystemState } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StudentStatusCard from '@/components/base/StudentStatusCard.vue'
import AnnouncementCard from '@/components/base/AnnouncementCard.vue'

const studentStore = useStudentStore()
const systemStateStore = useSystemStateStore()
const router = useRouter()

/* 系统阶段标签 — 复用 systemState store 的单一字典源 */
const phaseLabel = computed(() => systemStateStore.label)

/* 基础信息 — 从 studentStore.currentStudent 获取 */
const student = computed(() => studentStore.currentStudent)

/* 系统公告 — 仅展示已发布的（R7-02 / R7-03） */
const publishedAnnouncements = computed(() =>
  studentStore.announcements.filter((a) => a.published),
)

/* 快速操作入口 — 根据系统状态显示不同按钮 */
interface QuickAction {
  label: string
  path: string
}

const quickActions = computed<QuickAction[]>(() => {
  const state = studentStore.systemState
  if (state === SystemState.FIRST_ROUND_OPEN) {
    return [
      { label: '填报志愿', path: '/student/first-round/apply' },
      { label: '导师列表', path: '/student/teachers' },
    ]
  }
  if (state === SystemState.TEACHER_REVIEW) {
    return [
      { label: '查看志愿', path: '/student/first-round/my' },
      { label: '查看结果', path: '/student/first-round/result' },
    ]
  }
  if (state === SystemState.SECOND_ROUND_OPEN) {
    /* 仅第一轮被拒学生可参加第二轮 */
    if (studentStore.isRejectedInRound1) {
      return [{ label: '二轮导师列表', path: '/student/second-round/teachers' }]
    }
    return []
  }
  if (state === SystemState.FINISHED) {
    return [
      { label: '查看最终结果', path: '/student/final-result' },
      { label: '历史记录', path: '/student/history' },
    ]
  }
  return []
})

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">学生首页</h1>
    <p class="page-description">展示系统状态、个人状态、公告和快捷入口</p>

    <div class="dashboard">
      <!-- 主区域 -->
      <div class="dashboard-main">
        <!-- 当前系统阶段提示 -->
        <AppCard variant="default">
          <div class="phase-block">
            <span class="phase-eyebrow">当前系统阶段</span>
            <div class="phase-label">{{ phaseLabel }}</div>
          </div>
        </AppCard>

        <!-- 学生状态卡片 -->
        <section class="section">
          <h2 class="section-title">我的状态</h2>
          <StudentStatusCard :status="studentStore.studentStatus" />
        </section>

        <!-- 基础信息区 -->
        <section class="section">
          <h2 class="section-title">基础信息</h2>
          <AppCard variant="default">
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">姓名</span>
                <span class="info-value">{{ student.name }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">专业</span>
                <span class="info-value">{{ student.major }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">年级</span>
                <span class="info-value">{{ student.grade }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">院系</span>
                <span class="info-value">{{ student.department }}</span>
              </div>
            </div>
          </AppCard>
        </section>

        <!-- 快速操作入口 -->
        <section v-if="quickActions.length" class="section">
          <h2 class="section-title">快速操作</h2>
          <div class="quick-actions">
            <AppButton
              v-for="action in quickActions"
              :key="action.path"
              variant="primary"
              @click="navigate(action.path)"
            >
              {{ action.label }}
            </AppButton>
          </div>
        </section>
      </div>

      <!-- 侧栏：系统公告 -->
      <aside class="dashboard-sidebar">
        <h2 class="section-title">系统公告</h2>
        <div v-if="publishedAnnouncements.length" class="announcement-list">
          <AnnouncementCard
            v-for="item in publishedAnnouncements"
            :key="item.id"
            :title="item.title"
            :content="item.content"
            :created-at="item.createdAt"
          />
        </div>
        <p v-else class="empty-text">暂无公告</p>
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

/* 两列布局：主区域 + 侧栏 */
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

/* 公告列表 */
.announcement-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.empty-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

/* 响应式：单列 */
@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: 1fr;
  }
}
</style>
