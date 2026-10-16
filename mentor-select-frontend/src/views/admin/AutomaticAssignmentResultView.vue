<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import { AssignmentSource } from '@/types'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import AutoAssignSummary from '@/components/base/AutoAssignSummary.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const adminStore = useAdminStore()

const logId = computed(() => Number(route.query.logId))

const log = computed(() =>
  adminStore.autoAssignmentLogs.find((l) => l.id === logId.value) ?? null,
)

/* 该批次的分配结果 */
const assignments = computed(() => {
  if (!log.value) return []
  return adminStore.admissions
    .filter(
      (a) =>
        a.autoAssignmentLogId === log.value!.id &&
        a.source === AssignmentSource.AUTO_ASSIGNED,
    )
    .map((a) => {
      const student = adminStore.students.find((s) => s.id === a.studentId)
      const teacher = adminStore.teachers.find((t) => t.id === a.teacherId)
      return {
        studentId: a.studentId,
        studentName: student?.name ?? '未知',
        teacherId: a.teacherId,
        teacherName: teacher?.name ?? '未知',
      }
    })
})

/* 失败学生（未匹配且该批次未分配成功） */
const failedStudents = computed(() => {
  if (!log.value) return []
  return adminStore.unmatchedStudents.map((s) => ({
    id: s.id,
    name: s.name,
    studentId: s.studentId,
    major: s.major,
  }))
})

const showFailedPanel = ref(false)

async function handleRevoke(id: number) {
  const ok = await adminStore.revokeAutoAssign(id)
  if (!ok) {
    alert('撤销失败：该批次可能已被撤销')
    return
  }
  alert('已撤销整批自动分配，所有自动分配的学生已回到未匹配状态')
}

function handleExport() {
  const headers = ['学生姓名', '导师姓名']
  const rows = assignments.value.map((a) => [a.studentName, a.teacherName])
  const csv = [headers, ...rows].map((row) => row.map((c) => `"${c}"`).join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `auto-assignment-${logId.value}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

function goBack() {
  router.push('/admin/auto-assignment')
}

/* 跳转到人工分配页进行再次调整 */
function goToManualAssignment() {
  router.push('/admin/manual-assignment')
}
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <AppButton variant="tertiary" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </AppButton>
      <h1 class="page-title">自动分配结果</h1>
    </div>

    <template v-if="log">
      <!-- 摘要 -->
      <section class="section">
        <h2 class="section-title">批次摘要</h2>
        <AutoAssignSummary
          :log="log"
          :assignments="assignments"
          @revoke="handleRevoke"
          @export="handleExport"
        />
      </section>

      <!-- 失败学生 -->
      <section v-if="log.failedCount > 0" class="section">
        <div class="section-header">
          <h2 class="section-title">分配失败学生</h2>
          <AppButton variant="tertiary" @click="showFailedPanel = !showFailedPanel">
            {{ showFailedPanel ? '收起' : '展开' }}
          </AppButton>
        </div>
        <AppCard v-if="showFailedPanel" variant="default">
          <div v-if="failedStudents.length" class="failed-table">
            <div class="table-header">
              <div class="col-id">学号</div>
              <div class="col-name">姓名</div>
              <div class="col-major">专业</div>
              <div class="col-action">操作</div>
            </div>
            <div v-for="s in failedStudents" :key="s.id" class="table-row">
              <div class="col-id">{{ s.studentId }}</div>
              <div class="col-name">{{ s.name }}</div>
              <div class="col-major">{{ s.major }}</div>
              <div class="col-action">
                <AppButton variant="tertiary" @click="goToManualAssignment">
                  人工调整
                </AppButton>
              </div>
            </div>
          </div>
          <EmptyState v-else title="暂无失败学生" description="所有未匹配学生均已成功分配" />
        </AppCard>
      </section>

      <!-- 再次人工调整 -->
      <section class="section">
        <div class="actions">
          <AppButton variant="primary" @click="goToManualAssignment">
            前往人工分配页再次调整
          </AppButton>
        </div>
      </section>
    </template>

    <AppCard v-else variant="default">
      <EmptyState title="未找到批次" description="该批次不存在或已被删除">
        <AppButton variant="primary" @click="goBack">返回列表</AppButton>
      </EmptyState>
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.page-title {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
}

.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.failed-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr 1fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.table-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.table-row {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.table-row:last-child {
  border-bottom: none;
}

.col-name {
  font-weight: 500;
  color: var(--color-ink);
}

.actions {
  display: flex;
  justify-content: flex-end;
}
</style>
