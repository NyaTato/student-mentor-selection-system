<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { SystemState } from '@/types'
import { Check, Close } from '@element-plus/icons-vue'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import StateRollbackDialog from '@/components/base/StateRollbackDialog.vue'
import StateHistoryTimeline from '@/components/base/StateHistoryTimeline.vue'

const adminStore = useAdminStore()

/* 状态标签 & 推进顺序 — 从 store 消费（PROJECT.md 4.1，避免重复定义） */
const stateLabels = adminStore.stateLabel
const stateOrder = adminStore.stateOrder

const currentIndex = computed(() => stateOrder.indexOf(adminStore.systemState))

interface TimelineItem {
  state: SystemState
  label: string
  completed: boolean
  current: boolean
}

const timelineItems = computed<TimelineItem[]>(() =>
  stateOrder.map((state, idx) => ({
    state,
    label: stateLabels[state],
    completed: idx < currentIndex.value,
    current: idx === currentIndex.value,
  })),
)

/* 当前状态徽章变体 */
const currentStateVariant = computed<'success' | 'warning' | 'default'>(() => {
  switch (adminStore.systemState) {
    case SystemState.FINISHED:
      return 'success'
    case SystemState.INIT:
      return 'default'
    default:
      return 'warning'
  }
})

/* 下一状态 */
const nextState = computed(() => adminStore.nextState)
const nextStateLabel = computed(() =>
  nextState.value ? stateLabels[nextState.value] : '—',
)

/* 上一状态（用于回退） */
const previousState = computed(() => adminStore.previousState)
const previousStateLabel = computed(() =>
  previousState.value ? stateLabels[previousState.value] : '—',
)

/* INIT → FIRST_ROUND_OPEN 前置条件检查（PROJECT.md 4.2） */
const teacherCount = computed(() => adminStore.teachers.length)
const studentCount = computed(() => adminStore.students.length)
const hasTeachers = computed(() => teacherCount.value >= 1)
const hasStudents = computed(() => studentCount.value >= 1)
const initPreconditionMet = computed(() => hasTeachers.value && hasStudents.value)

const showInitPrecondition = computed(
  () => adminStore.systemState === SystemState.INIT,
)

/* 推进按钮禁用条件 */
const advanceDisabled = computed(() => {
  if (!adminStore.canAdvanceState) return true
  if (adminStore.systemState === SystemState.INIT && !initPreconditionMet.value) {
    return true
  }
  return false
})

/* 状态转换规则 — PROJECT.md 4.2 */
interface TransitionRule {
  fromLabel: string
  toLabel: string
  precondition: string
  current: boolean
}

const transitionRules = computed<TransitionRule[]>(() => {
  const base: Array<{
    from: SystemState
    to: SystemState | null
    precondition: string
  }> = [
    {
      from: SystemState.INIT,
      to: SystemState.FIRST_ROUND_OPEN,
      precondition: '至少 1 名导师和 1 名学生',
    },
    {
      from: SystemState.FIRST_ROUND_OPEN,
      to: SystemState.TEACHER_REVIEW,
      precondition: '—',
    },
    {
      from: SystemState.TEACHER_REVIEW,
      to: SystemState.SECOND_ROUND_OPEN,
      precondition: '所有导师均已提交筛选结果',
    },
    {
      from: SystemState.SECOND_ROUND_OPEN,
      to: SystemState.AUTO_ASSIGN,
      precondition: '—',
    },
    {
      from: SystemState.AUTO_ASSIGN,
      to: SystemState.FINISHED,
      precondition: '—',
    },
    {
      from: SystemState.FINISHED,
      to: null,
      precondition: '终态，无后续状态',
    },
  ]
  return base.map((r) => ({
    fromLabel: stateLabels[r.from],
    toLabel: r.to ? stateLabels[r.to] : '终态',
    precondition: r.precondition,
    current: r.from === adminStore.systemState,
  }))
})

/* 推进状态 */
async function handleAdvance() {
  if (advanceDisabled.value) return
  const fromLabel = adminStore.currentStateLabel
  const toLabel = nextStateLabel.value
  if (
    !confirm(
      `确认将系统状态从「${fromLabel}」推进到「${toLabel}」？`,
    )
  ) {
    return
  }
  const ok = await adminStore.advanceState()
  if (!ok) {
    alert('状态推进失败：前置条件未满足')
    return
  }
  alert(`状态已推进到「${toLabel}」`)
}

/* ========== 状态回退（R12-01 ~ R12-08） ========== */
const rollbackDialogVisible = ref(false)

function openRollbackDialog() {
  if (!adminStore.canRollbackState) return
  rollbackDialogVisible.value = true
}

async function handleRollbackConfirm(reason: string) {
  if (!previousState.value) return
  /* 保存回退前的目标状态标签 — rollbackState 成功后 systemState 会更新，
     previousStateLabel 会重新计算，导致提示与实际回退阶段不一致 */
  const targetLabel = previousStateLabel.value
  const ok = await adminStore.rollbackState(reason)
  if (!ok) {
    alert('回退失败：原因不合规或无上一状态')
    return
  }
  alert(`状态已回退到「${targetLabel}」`)
}

/* ========== 状态变更历史 ========== */
const stateHistories = computed(() => adminStore.stateHistory)
</script>

<template>
  <div class="page-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">状态控制</h1>
      <p class="page-description">推进系统状态</p>
    </div>

    <!-- 当前状态卡片 -->
    <section class="section">
      <h2 class="section-title">当前状态</h2>
      <AppCard variant="default">
        <div class="current-state-content">
          <div class="current-state-info">
            <span class="current-state-eyebrow">系统当前阶段</span>
            <span class="current-state-value">{{ adminStore.currentStateLabel }}</span>
          </div>
          <StatusBadge
            :variant="currentStateVariant"
            :label="adminStore.currentStateLabel"
          />
        </div>
      </AppCard>
    </section>

    <!-- 状态推进时间线 -->
    <section class="section">
      <h2 class="section-title">状态推进时间线</h2>
      <AppCard variant="default">
        <div class="timeline">
          <div
            v-for="(item, idx) in timelineItems"
            :key="item.state"
            class="timeline-step"
            :class="{
              'timeline-step-completed': item.completed,
              'timeline-step-current': item.current,
            }"
          >
            <div class="timeline-marker">
              <el-icon v-if="item.completed" class="timeline-check"><Check /></el-icon>
              <span v-else class="timeline-index">{{ idx + 1 }}</span>
            </div>
            <div class="timeline-label">{{ item.label }}</div>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 下一阶段卡片 -->
    <section class="section">
      <h2 class="section-title">下一阶段</h2>
      <AppCard variant="default">
        <div class="next-state-content">
          <div class="next-state-flow">
            <div class="next-state-block">
              <span class="next-state-block-label">当前状态</span>
              <span class="next-state-block-value">{{ adminStore.currentStateLabel }}</span>
            </div>
            <span class="next-state-arrow" aria-hidden="true">→</span>
            <div class="next-state-block">
              <span class="next-state-block-label">下一状态</span>
              <span
                class="next-state-block-value"
                :class="{ 'next-state-block-value-empty': !nextState }"
              >
                {{ nextStateLabel }}
              </span>
            </div>
          </div>
          <div class="next-state-action">
            <AppButton
              variant="danger"
              :disabled="!adminStore.canRollbackState"
              @click="openRollbackDialog"
            >
              回退到上一阶段
            </AppButton>
            <AppButton
              variant="primary"
              :disabled="advanceDisabled"
              @click="handleAdvance"
            >
              推进到下一阶段
            </AppButton>
          </div>
        </div>

        <!-- INIT → FIRST_ROUND_OPEN 前置条件检查 -->
        <div v-if="showInitPrecondition" class="precondition-block">
          <h3 class="precondition-title">前置条件检查</h3>
          <div class="precondition-list">
            <div
              class="precondition-item"
              :class="{ 'precondition-met': hasTeachers }"
            >
              <el-icon class="precondition-icon"><Check v-if="hasTeachers" /><Close v-else /></el-icon>
              <span class="precondition-text">
                至少 1 名导师（当前：{{ teacherCount }} 名）
              </span>
            </div>
            <div
              class="precondition-item"
              :class="{ 'precondition-met': hasStudents }"
            >
              <el-icon class="precondition-icon"><Check v-if="hasStudents" /><Close v-else /></el-icon>
              <span class="precondition-text">
                至少 1 名学生（当前：{{ studentCount }} 名）
              </span>
            </div>
          </div>
          <p v-if="!initPreconditionMet" class="precondition-warning">
            前置条件未满足，暂无法推进状态
          </p>
        </div>
      </AppCard>
    </section>

    <!-- 状态转换规则表 -->
    <section class="section">
      <h2 class="section-title">状态转换规则</h2>
      <AppCard variant="default">
        <div class="rules-table">
          <div class="rules-row rules-row-header">
            <div class="rules-cell">起始状态</div>
            <div class="rules-cell">目标状态</div>
            <div class="rules-cell">前置条件</div>
          </div>
          <div
            v-for="(rule, idx) in transitionRules"
            :key="idx"
            class="rules-row"
            :class="{ 'rules-row-current': rule.current }"
          >
            <div class="rules-cell">{{ rule.fromLabel }}</div>
            <div class="rules-cell">{{ rule.toLabel }}</div>
            <div class="rules-cell">{{ rule.precondition }}</div>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 状态变更历史 -->
    <section class="section">
      <h2 class="section-title">状态变更历史</h2>
      <AppCard variant="default">
        <StateHistoryTimeline :histories="stateHistories" :state-labels="stateLabels" />
      </AppCard>
    </section>

    <!-- 状态回退确认弹窗 -->
    <StateRollbackDialog
      v-model:visible="rollbackDialogVisible"
      :from-label="adminStore.currentStateLabel"
      :to-label="previousStateLabel"
      @confirm="handleRollbackConfirm"
    />
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

/* 当前状态卡片 */
.current-state-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.current-state-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.current-state-eyebrow {
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  letter-spacing: var(--text-eyebrow-spacing);
  color: var(--color-ink-subtle);
  text-transform: uppercase;
}

.current-state-value {
  font-size: var(--text-display-md);
  font-weight: var(--text-display-md-weight);
  line-height: var(--text-display-md-line);
  letter-spacing: var(--text-display-md-spacing);
  color: var(--color-ink);
}

/* 时间线 */
.timeline {
  display: flex;
  align-items: flex-start;
  width: 100%;
}

.timeline-step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  min-width: 0;
}

.timeline-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 18px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--color-hairline);
  z-index: 0;
}

.timeline-step-completed:not(:last-child)::after {
  background: var(--color-semantic-success);
}

.timeline-marker {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-surface-3);
  color: var(--color-ink-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-body-sm);
  font-weight: 600;
  z-index: 1;
  border: 2px solid var(--color-surface-3);
  transition: background 0.15s, color 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.timeline-check {
  font-size: 16px;
  line-height: 1;
}

.timeline-step-completed .timeline-marker {
  background: var(--color-semantic-success);
  border-color: var(--color-semantic-success);
  color: var(--color-surface-1);
}

.timeline-step-current .timeline-marker {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: var(--color-surface-1);
  box-shadow: 0 0 0 4px var(--color-primary-soft);
}

.timeline-label {
  margin-top: var(--spacing-sm);
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
  text-align: center;
  line-height: var(--text-body-sm-line);
  word-break: break-word;
}

.timeline-step-completed .timeline-label,
.timeline-step-current .timeline-label {
  color: var(--color-ink);
  font-weight: 500;
}

/* 下一阶段卡片 */
.next-state-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.next-state-flow {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.next-state-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.next-state-block-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.next-state-block-value {
  font-size: var(--text-subhead);
  font-weight: 600;
  color: var(--color-ink);
}

.next-state-block-value-empty {
  color: var(--color-ink-tertiary);
}

.next-state-arrow {
  font-size: var(--text-headline);
  color: var(--color-ink-subtle);
  font-weight: 300;
}

.next-state-action {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

/* 前置条件检查 */
.precondition-block {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-hairline);
}

.precondition-title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: var(--spacing-sm);
}

.precondition-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.precondition-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--rounded-md);
  background: var(--color-surface-2);
}

.precondition-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
  flex-shrink: 0;
}

.precondition-met .precondition-icon {
  background: var(--color-success-bg);
  color: var(--color-semantic-success);
}

.precondition-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.precondition-warning {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-warning-bg);
  color: var(--color-semantic-warning);
  border-radius: var(--rounded-md);
  font-size: var(--text-body-sm);
}

/* 状态转换规则表 */
.rules-table {
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  overflow: hidden;
}

.rules-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr;
  border-bottom: 1px solid var(--color-hairline);
}

.rules-row:last-child {
  border-bottom: none;
}

.rules-row-header {
  background: var(--color-surface-2);
}

.rules-row-header .rules-cell {
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.rules-cell {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  word-break: break-word;
}

.rules-row-current {
  background: var(--color-primary-soft);
}

.rules-row-current .rules-cell {
  color: var(--color-primary-hover);
  font-weight: 500;
}

/* 响应式 */
@media (max-width: 760px) {
  .next-state-content {
    flex-direction: column;
    align-items: stretch;
  }
  .next-state-flow {
    justify-content: space-between;
  }
  .next-state-action {
    justify-content: flex-end;
  }
  .timeline-label {
    font-size: var(--text-caption);
  }
}
</style>
