<script setup lang="ts">
import { computed } from 'vue'
import { useTeacherStore } from '@/stores/teacher'
import { SystemState } from '@/types'
import { InfoFilled } from '@element-plus/icons-vue'
import AppCard from '@/components/base/AppCard.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import StatItem from '@/components/base/StatItem.vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAssignmentSourceBadge } from '@/utils/badges'

const teacherStore = useTeacherStore()

/* 系统完成后才显示最终分配结果（PROJECT.md 6.5） */
const isFinished = computed(() => teacherStore.systemState === SystemState.FINISHED)

/* 最终指导学生列表（包含所有录取来源：第一轮/第二轮/管理员分配） */
const assignedStudents = computed(() =>
  teacherStore.myAdmissions.map((adm) => {
    const student = teacherStore.getStudentById(adm.studentId)
    return {
      admissionId: adm.id,
      studentId: adm.studentId,
      studentName: student?.name ?? '未知',
      studentNumber: student?.studentId ?? '-',
      major: student?.major ?? '-',
      grade: student?.grade ?? '-',
      department: student?.department ?? '-',
      source: adm.source,
      assignedAt: adm.createdAt,
    }
  }),
)


</script>

<template>
  <div class="page-container">
    <h1 class="page-title">已指导学生</h1>
    <p class="page-description">最终指导学生名单（系统结束后只读）</p>

    <!-- 阶段提示 -->
    <StateNotice v-if="!isFinished" :icon="InfoFilled">
      系统尚未结束，当前名单可能仍会变化，最终名单以系统结束后的结果为准
    </StateNotice>

    <!-- 统计 -->
    <AppCard variant="default">
      <div class="summary-row">
        <StatItem label="已指导学生总数" :value="assignedStudents.length" />
        <StatItem label="招生名额" :value="teacherStore.quotaInfo.max" />
      </div>
    </AppCard>

    <!-- 学生列表 -->
    <section class="section">
      <h2 class="section-title">指导学生名单</h2>
      <AppCard variant="default">
        <div v-if="assignedStudents.length" class="student-table">
          <div class="student-table-header">
            <div class="col-student">学生</div>
            <div class="col-major">专业</div>
            <div class="col-grade">年级</div>
            <div class="col-department">院系</div>
            <div class="col-source">分配来源</div>
            <div class="col-time">分配时间</div>
          </div>
          <div
            v-for="item in assignedStudents"
            :key="item.admissionId"
            class="student-table-row"
          >
            <div class="col-student">
              <div class="student-name">{{ item.studentName }}</div>
              <div class="student-id">{{ item.studentNumber }}</div>
            </div>
            <div class="col-major">{{ item.major }}</div>
            <div class="col-grade">{{ item.grade }}</div>
            <div class="col-department">{{ item.department }}</div>
            <div class="col-source">
              <StatusBadge
                :variant="getAssignmentSourceBadge(item.source).variant"
                :label="getAssignmentSourceBadge(item.source).label"
              />
            </div>
            <div class="col-time">{{ formatDateTime(item.assignedAt) }}</div>
          </div>
        </div>
        <EmptyState v-else title="暂无指导学生" />
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

/* 统计 */
.summary-row {
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
.student-table {
  display: flex;
  flex-direction: column;
}

.student-table-header,
.student-table-row {
  display: grid;
  grid-template-columns: 1.4fr 1.4fr 0.8fr 1fr 1.2fr 1.4fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.student-table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: var(--text-eyebrow-spacing);
}

.student-table-row {
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.student-table-row:last-child {
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
.col-grade,
.col-department,
.col-time {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}
</style>
