<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
import type { SystemStateSchedule } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import ScheduleConfigTable from '@/components/base/ScheduleConfigTable.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import { formatDateTime } from '@/composables/useFormatTime'

const adminStore = useAdminStore()

/* 定时器 — 每 30s 扫描一次是否到达计划时间 */
let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  timer = setInterval(() => {
    adminStore.tickAutoTransition()
  }, 30000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})

/* 手动触发一次扫描 */
function handleTickNow() {
  const triggered = adminStore.tickAutoTransition()
  if (triggered) {
    alert('已触发自动状态切换')
  } else {
    alert('当前无需触发的自动切换')
  }
}

async function handleUpdateField(field: keyof SystemStateSchedule, value: string | null) {
  await adminStore.updateSchedule({ [field]: value } as Partial<SystemStateSchedule>)
}

async function handleToggleAuto(enabled: boolean) {
  await adminStore.toggleAutoSwitch(enabled)
}

const schedule = ref<SystemStateSchedule>(adminStore.systemStateSchedule)
const lastUpdated = ref(adminStore.systemStateSchedule.updatedAt)
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">时间切换配置</h1>
      <p class="page-description">配置系统状态的自动切换时间，到达计划时间将自动推进</p>
    </div>

    <!-- 阶段提示 -->
    <StateNotice>
      <StatusBadge variant="warning" label="定时调度" />
      <span>
        前端定时器每 30 秒扫描一次计划时间，到达计划时间将自动推进系统状态。
      </span>
    </StateNotice>

    <!-- 当前状态概览 -->
    <section class="section">
      <h2 class="section-title">当前状态概览</h2>
      <AppCard variant="default">
        <div class="overview-grid">
          <div class="overview-item">
            <span class="overview-label">系统状态</span>
            <span class="overview-value">{{ adminStore.currentStateLabel }}</span>
          </div>
          <div class="overview-item">
            <span class="overview-label">自动切换</span>
            <span
              :class="['overview-value', schedule.autoEnabled ? 'value-active' : 'value-inactive']"
            >
              {{ schedule.autoEnabled ? '已启用' : '已暂停' }}
            </span>
          </div>
          <div class="overview-item">
            <span class="overview-label">最后更新</span>
            <span class="overview-value">{{ formatDateTime(lastUpdated) }}</span>
          </div>
          <div class="overview-item">
            <span class="overview-label">当前学年</span>
            <span class="overview-value">{{ adminStore.currentAcademicYear?.name ?? '—' }}</span>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 配置表 -->
    <section class="section">
      <h2 class="section-title">自动切换配置</h2>
      <AppCard variant="default">
        <ScheduleConfigTable
          :schedule="schedule"
          :current-state="adminStore.systemState"
          :state-labels="adminStore.stateLabel"
          @update:field="handleUpdateField"
          @toggle-auto="handleToggleAuto"
        />
      </AppCard>
    </section>

    <!-- 手动扫描 -->
    <section class="section">
      <div class="manual-tick">
        <div class="manual-tick-info">
          <h3 class="manual-tick-title">手动触发扫描</h3>
          <p class="manual-tick-hint">
            立即扫描一次计划时间，无需等待 30 秒间隔（用于测试或紧急触发）
          </p>
        </div>
        <el-button type="primary" plain @click="handleTickNow">
          立即扫描
        </el-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
}

.page-header {
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

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--spacing-md);
}

.overview-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.overview-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.overview-value {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.value-active {
  color: var(--color-semantic-success);
}

.value-inactive {
  color: var(--color-ink-tertiary);
}

.manual-tick {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-surface-2);
  border-radius: var(--rounded-md);
  border: 1px solid var(--color-hairline);
}

.manual-tick-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.manual-tick-title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.manual-tick-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

@media (max-width: 600px) {
  .manual-tick {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
