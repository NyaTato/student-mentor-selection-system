<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTeacherStore } from '@/stores/teacher'
import { SystemState, AssignmentSource } from '@/types'
import { CircleCheckFilled, InfoFilled } from '@element-plus/icons-vue'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import StatItem from '@/components/base/StatItem.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAssignmentSourceBadge } from '@/utils/badges'

const teacherStore = useTeacherStore()
const isRevoking = ref(false)

/* 仅在导师筛选阶段允许修改录取名单（R2-04） */
const canModify = computed(() => teacherStore.systemState === SystemState.TEACHER_REVIEW)

const quota = computed(() => teacherStore.quotaInfo)

/* 已录取列表 */
const admittedList = computed(() =>
  teacherStore.myAdmissions.map((adm) => {
    const student = teacherStore.getStudentById(adm.studentId)
    const application = teacherStore.applications.find(
      (a) => a.studentId === adm.studentId && a.teacherId === adm.teacherId,
    )
    return {
      admissionId: adm.id,
      applicationId: adm.applicationId,
      studentId: adm.studentId,
      studentName: student?.name ?? '未知',
      studentNumber: student?.studentId ?? '-',
      major: student?.major ?? '-',
      source: adm.source,
      admittedAt: adm.createdAt,
      applicationTime: application?.createdAt ?? '-',
    }
  }),
)

/* 撤销录取 — 导师筛选阶段内可修改（R2-04） */
async function handleRevoke(admissionId: number) {
  if (isRevoking.value) return
  if (!confirm('确认撤销该学生的录取？撤销后该学生将进入第二轮。')) return
  isRevoking.value = true
  try {
    const ok = await teacherStore.revokeAdmission(admissionId)
    if (!ok) alert('撤销未完成，请刷新页面核对申请状态')
  } finally {
    isRevoking.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">录取管理</h1>
    <p class="page-description">确认和修改录取名单</p>

    <!-- 名额概览 -->
    <AppCard variant="default">
      <div class="quota-overview">
        <div class="quota-summary">
          <StatItem label="招生名额" :value="quota.max" />
          <StatItem label="已录取" :value="quota.admitted" tone="success" />
          <StatItem
            label="剩余"
            :value="quota.remaining"
            :tone="quota.remaining <= 0 ? 'error' : 'default'"
          />
        </div>
        <QuotaBadge :admitted="quota.admitted" :max="quota.max" />
      </div>
    </AppCard>

    <!-- 阶段提示 -->
    <StateNotice v-if="!canModify" :icon="InfoFilled">
      当前阶段录取名单已锁定，不可修改
    </StateNotice>

    <StateNotice v-else-if="quota.remaining <= 0" variant="success" :icon="CircleCheckFilled">
      已达招生名额上限，无法继续录取
    </StateNotice>

    <!-- 已录取学生列表 -->
    <section class="section">
      <h2 class="section-title">已录取学生（{{ admittedList.length }}）</h2>
      <AppCard variant="default">
        <div v-if="admittedList.length" class="admit-table">
          <div class="admit-table-header">
            <div class="col-student">学生</div>
            <div class="col-major">专业</div>
            <div class="col-source">录取来源</div>
            <div class="col-time">录取时间</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="item in admittedList" :key="item.admissionId" class="admit-table-row">
            <div class="col-student">
              <div class="student-name">{{ item.studentName }}</div>
              <div class="student-id">{{ item.studentNumber }}</div>
            </div>
            <div class="col-major">{{ item.major }}</div>
            <div class="col-source">
              <StatusBadge
                :variant="getAssignmentSourceBadge(item.source).variant"
                :label="getAssignmentSourceBadge(item.source).label"
              />
            </div>
            <div class="col-time">{{ item.admittedAt === '-' ? '-' : formatDateTime(item.admittedAt) }}</div>
            <div class="col-action">
              <AppButton
                v-if="canModify && item.source === AssignmentSource.ROUND1 && item.applicationId !== null"
                variant="danger"
                :disabled="isRevoking"
                @click="handleRevoke(item.admissionId)"
              >
                撤销录取
              </AppButton>
              <span v-else class="action-readonly">—</span>
            </div>
          </div>
        </div>
        <EmptyState v-else title="暂无已录取学生" />
      </AppCard>
    </section>
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

/* 名额概览 */
.quota-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.quota-summary {
  display: flex;
  gap: var(--spacing-xl);
}

/* 列表 */
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

/* 表格 */
.admit-table {
  display: flex;
  flex-direction: column;
}

.admit-table-header,
.admit-table-row {
  display: grid;
  grid-template-columns: 1.5fr 1.5fr 1.2fr 1.5fr 1fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.admit-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.admit-table-row {
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.admit-table-row:last-child {
  border-bottom: none;
}

.col-student {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.student-name {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.student-id {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.col-major,
.col-time {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.action-readonly {
  color: var(--color-ink-tertiary);
}
</style>
