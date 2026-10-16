<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { SystemState, type StudentInfo } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'
import StateNotice from '@/components/base/StateNotice.vue'
import { Close } from '@element-plus/icons-vue'
import { formatDateTime } from '@/composables/useFormatTime'
import { getAutoAssignmentStatusBadge } from '@/utils/badges'

const adminStore = useAdminStore()
const router = useRouter()

/* ========== 阶段提示 ==========
 * PROJECT.md 7.11 / 9.5：人工分配仅在 AUTO_ASSIGN 或 FINISHED 阶段可用
 * 不在上述阶段时，分配按钮禁用（仅允许查看未匹配学生与可分配导师）
 */
const isInAssignmentPhase = computed(
  () =>
    adminStore.systemState === SystemState.AUTO_ASSIGN ||
    adminStore.systemState === SystemState.FINISHED,
)

/* ========== 未匹配学生 & 可分配导师 ========== */
const unmatchedStudents = computed(() => adminStore.unmatchedStudents)
const availableTeachers = computed(() => adminStore.availableTeachers)

/* ========== 分配弹窗 ========== */
const modalVisible = ref(false)
const selectedStudent = ref<StudentInfo | null>(null)
const selectedTeacherId = ref<number | null>(null)

/* 提交中标记 — 阻止重复提交（人工分配是写操作，重复提交会打出两个请求） */
const isSubmitting = ref(false)

function openAssignModal(student: StudentInfo) {
  selectedStudent.value = student
  selectedTeacherId.value = null
  modalVisible.value = true
}

function closeModal() {
  /* 提交中不允许关闭弹窗 — 否则请求返回后会对已关闭的弹窗做状态更新 */
  if (isSubmitting.value) return
  modalVisible.value = false
  selectedStudent.value = null
  selectedTeacherId.value = null
}

/* R8-03：所选导师必须仍有剩余名额 */
const selectedTeacher = computed(
  () => availableTeachers.value.find((t) => t.id === selectedTeacherId.value) ?? null,
)

function canConfirm(): boolean {
  return selectedStudent.value !== null && selectedTeacher.value !== null
}

/* R8-04：分配即时生效；R8-05：来源由 store 标记为「管理员人工分配」 */
async function handleConfirm() {
  /* 已在提交中 — 直接忽略重复点击 */
  if (isSubmitting.value) return
  if (!selectedStudent.value) {
    alert('未选择学生')
    return
  }
  if (!selectedTeacherId.value) {
    alert('请选择导师')
    return
  }
  const student = selectedStudent.value
  const teacherId = selectedTeacherId.value
  /* R8-03：再次校验剩余名额（防止并发变更） */
  const teacher = availableTeachers.value.find((t) => t.id === teacherId)
  if (!teacher || teacher.remaining <= 0) {
    alert(`导师「${teacher?.name ?? teacherId}」已无剩余名额，请重新选择`)
    return
  }
  /* R8-02：仅未匹配学生可分配（store 内部再次校验）
   * 必须 await：只有后端 POST 成功（并已用服务端数据刷新录取与名额）才算成功，
   * 不做任何本地乐观更新 / 伪造成功。 */
  isSubmitting.value = true
  let assigned = false
  try {
    assigned = await adminStore.manualAssign(student.id, teacherId)
    if (!assigned) {
      alert('分配失败：该学生可能已被分配，或导师名额已满')
    }
  } catch {
    alert('分配请求已提交，但刷新结果失败，请重新打开页面核对录取状态')
  } finally {
    isSubmitting.value = false
  }
  if (assigned) {
    alert(`已将学生「${student.name}」分配给导师「${teacher.name}」`)
    closeModal()
  }
}

/* ========== 自动分配入口（PROJECT.md 3.5 / R10-01 ~ R10-11） ========== */
const isExecutingAuto = ref(false)

async function handleAutoAssign() {
  if (adminStore.isAutoAssignRunning) {
    alert('已有自动分配任务正在运行，请等待完成')
    return
  }
  const preview = adminStore.autoAssignPreview
  if (preview.totalCandidates === 0) {
    alert('当前没有未匹配学生需要分配')
    return
  }
  if (
    !confirm(
      `确认执行自动分配？\n未匹配学生：${preview.totalCandidates} 人\n预计可分配：${preview.assignableCount} 人`,
    )
  )
    return
  isExecutingAuto.value = true
  try {
    const result = await adminStore.executeAutoAssign()
    if (!result.success) {
      alert(result.message)
      return
    }
    alert(result.message)
    if (result.logId) {
      router.push(`/admin/auto-assignment-result?logId=${result.logId}`)
    }
  } finally {
    isExecutingAuto.value = false
  }
}

/* 自动分配历史日志 */
const autoAssignLogs = computed(() => adminStore.autoAssignmentLogs)

function viewAutoResult(logId: number) {
  router.push(`/admin/auto-assignment-result?logId=${logId}`)
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">人工分配</h1>
    <p class="page-description">为未匹配学生人工分配导师</p>

    <!-- 阶段提示 -->
    <StateNotice v-if="!isInAssignmentPhase">
      <StatusBadge variant="warning" label="阶段提示" />
      <span>
        当前系统状态为「{{ adminStore.currentStateLabel }}」，人工分配仅在自动分配阶段或系统结束后可用，当前分配按钮已禁用。
      </span>
    </StateNotice>

    <!-- 自动分配入口 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">自动分配</h2>
      </div>
      <AppCard variant="default">
        <div class="auto-assign-info">
          <div class="auto-assign-stats">
            <div class="auto-stat">
              <span class="auto-stat-label">未匹配学生</span>
              <span class="auto-stat-value">{{ adminStore.autoAssignPreview.totalCandidates }}</span>
            </div>
            <div class="auto-stat">
              <span class="auto-stat-label">预计可分配</span>
              <span class="auto-stat-value">{{ adminStore.autoAssignPreview.assignableCount }}</span>
            </div>
            <div class="auto-stat">
              <span class="auto-stat-label">总剩余名额</span>
              <span class="auto-stat-value">{{ adminStore.autoAssignPreview.totalRemaining }}</span>
            </div>
          </div>
          <div class="auto-assign-actions">
            <AppButton
              variant="primary"
              :disabled="!isInAssignmentPhase || isExecutingAuto || adminStore.isAutoAssignRunning"
              @click="handleAutoAssign"
            >
              {{ isExecutingAuto ? '分配中…' : '执行自动分配' }}
            </AppButton>
            <AppButton variant="secondary" @click="router.push('/admin/auto-assignment')">
              查看自动分配页
            </AppButton>
          </div>
        </div>
        <p v-if="adminStore.autoAssignPreview.isInsufficient" class="auto-warning">
          导师总剩余名额不足，部分学生可能无法分配
        </p>
      </AppCard>
    </section>

    <!-- 未匹配学生 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">未匹配学生</h2>
        <span class="section-count">共 {{ unmatchedStudents.length }} 人</span>
      </div>
      <AppCard variant="default">
        <div v-if="unmatchedStudents.length" class="student-table">
          <div class="table-header">
            <div class="col-studentid">学号</div>
            <div class="col-name">姓名</div>
            <div class="col-major">专业</div>
            <div class="col-grade">年级</div>
            <div class="col-dept">院系</div>
            <div class="col-phone">电话</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="s in unmatchedStudents" :key="s.id" class="table-row">
            <div class="col-studentid">{{ s.studentId }}</div>
            <div class="col-name">{{ s.name }}</div>
            <div class="col-major">{{ s.major }}</div>
            <div class="col-grade">{{ s.grade }}</div>
            <div class="col-dept">{{ s.department }}</div>
            <div class="col-phone">{{ s.phone }}</div>
            <div class="col-action">
              <AppButton
                variant="primary"
                :disabled="availableTeachers.length === 0 || !isInAssignmentPhase"
                @click="openAssignModal(s)"
              >
                分配导师
              </AppButton>
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无未匹配学生"
          description="所有学生均已匹配导师"
        />
      </AppCard>
    </section>

    <!-- 可分配导师 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">可分配导师</h2>
        <span class="section-count">共 {{ availableTeachers.length }} 人</span>
      </div>
      <AppCard variant="default">
        <div v-if="availableTeachers.length" class="teacher-table">
          <div class="table-header">
            <div class="col-name">姓名</div>
            <div class="col-dept">院系</div>
            <div class="col-title">职称</div>
            <div class="col-quota">名额</div>
          </div>
          <div v-for="t in availableTeachers" :key="t.id" class="table-row">
            <div class="col-name">{{ t.name }}</div>
            <div class="col-dept">{{ t.department }}</div>
            <div class="col-title">{{ t.title }}</div>
            <div class="col-quota">
              <QuotaBadge :admitted="t.currentAdmitted" :max="t.maxQuota" />
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无可分配导师"
          description="所有导师名额已满，无法进行人工分配"
        />
      </AppCard>
    </section>

    <!-- 自动分配日志 -->
    <section v-if="autoAssignLogs.length" class="section">
      <div class="section-header">
        <h2 class="section-title">自动分配日志</h2>
        <span class="section-count">共 {{ autoAssignLogs.length }} 个批次</span>
      </div>
      <AppCard variant="default">
        <div class="log-table">
          <div class="log-header">
            <div class="log-col-id">批次</div>
            <div class="log-col-status">状态</div>
            <div class="log-col-candidates">候选</div>
            <div class="log-col-assigned">成功</div>
            <div class="log-col-failed">失败</div>
            <div class="log-col-time">时间</div>
            <div class="log-col-action">操作</div>
          </div>
          <div v-for="log in autoAssignLogs" :key="log.id" class="log-row">
            <div class="log-col-id">#{{ log.id }}</div>
            <div class="log-col-status">
              <StatusBadge :variant="getAutoAssignmentStatusBadge(log.status).variant" :label="getAutoAssignmentStatusBadge(log.status).label" />
            </div>
            <div class="log-col-candidates">{{ log.totalCandidates }}</div>
            <div class="log-col-assigned">{{ log.assignedCount }}</div>
            <div class="log-col-failed">{{ log.failedCount }}</div>
            <div class="log-col-time">{{ formatDateTime(log.createdAt) }}</div>
            <div class="log-col-action">
              <AppButton variant="tertiary" @click="viewAutoResult(log.id)">
                查看结果
              </AppButton>
            </div>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 分配弹窗 -->
    <Teleport to="body">
      <div v-if="modalVisible" class="dialog-overlay" @click="closeModal">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">分配导师</h2>
            <el-icon class="close-btn" @click="closeModal"><Close /></el-icon>
          </div>
          <div class="dialog-body">
            <!-- 学生信息摘要 -->
            <div v-if="selectedStudent" class="student-summary">
              <div class="summary-row">
                <span class="summary-label">学生姓名</span>
                <span class="summary-value">{{ selectedStudent.name }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">学号</span>
                <span class="summary-value">{{ selectedStudent.studentId }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">专业</span>
                <span class="summary-value">{{ selectedStudent.major }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">院系</span>
                <span class="summary-value">{{ selectedStudent.department }}</span>
              </div>
            </div>

            <!-- 导师选择 -->
            <div class="form-field">
              <label class="form-label">选择导师</label>
              <el-select v-model="selectedTeacherId" placeholder="请选择导师">
                <el-option
                  v-for="t in availableTeachers"
                  :key="t.id"
                  :label="`${t.name}（${t.department} · ${t.title}）剩余 ${t.remaining}`"
                  :value="t.id"
                />
              </el-select>
              <div v-if="selectedTeacher" class="teacher-quota-hint">
                <QuotaBadge
                  :admitted="selectedTeacher.currentAdmitted"
                  :max="selectedTeacher.maxQuota"
                />
              </div>
            </div>
          </div>
          <div class="dialog-footer">
            <AppButton
              type="button"
              variant="tertiary"
              :disabled="isSubmitting"
              @click="closeModal"
            >
              取消
            </AppButton>
            <AppButton
              type="button"
              variant="primary"
              :disabled="!canConfirm() || isSubmitting"
              @click="handleConfirm"
            >
              {{ isSubmitting ? '分配中…' : '确认分配' }}
            </AppButton>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1200px;
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

/* Section */
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
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.section-count {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

/* 表格通用 — CSS Grid */
.student-table,
.teacher-table {
  display: flex;
  flex-direction: column;
}

.student-table .table-header,
.student-table .table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr 0.8fr 1.2fr 1.2fr 1fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.teacher-table .table-header,
.teacher-table .table-row {
  display: grid;
  grid-template-columns: 1fr 1.4fr 1fr 1.6fr;
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
  letter-spacing: var(--text-eyebrow-spacing);
}

.table-row {
  padding: var(--spacing-md) 0;
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

.col-action {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

/* 弹窗 */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-semantic-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--spacing-md);
}

.dialog-content {
  background: var(--color-card);
  border-radius: var(--rounded-xl);
  box-shadow: var(--shadow-lg);
  width: 520px;
  max-width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-hairline);
}

.dialog-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--color-ink-subtle);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--rounded-sm);
  transition: background 0.15s;
}

.close-btn:hover {
  background: var(--color-surface-3);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* 学生信息摘要 */
.student-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm) var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-surface-2);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
}

.summary-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.summary-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.summary-value {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

/* 表单字段 */
.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.form-select {
  background: var(--color-surface-1);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  padding: var(--spacing-xs) var(--spacing-sm);
  color: var(--color-ink);
  font-size: var(--text-body);
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.form-select:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.teacher-quota-hint {
  display: flex;
  align-items: center;
}

/* 弹窗底部 */
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-top: var(--spacing-md);
}

/* 自动分配区 */
.auto-assign-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.auto-assign-stats {
  display: flex;
  gap: var(--spacing-lg);
}

.auto-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-stat-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.auto-stat-value {
  font-size: var(--text-headline);
  font-weight: 600;
  color: var(--color-ink);
}

.auto-assign-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.auto-warning {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-warning-bg);
  color: var(--color-semantic-warning);
  border-radius: var(--rounded-sm);
  font-size: var(--text-body-sm);
}

/* 自动分配日志表 */
.log-table {
  display: flex;
  flex-direction: column;
}

.log-header,
.log-row {
  display: grid;
  grid-template-columns: 80px 110px 80px 80px 80px 1.4fr 1fr;
  gap: var(--spacing-sm);
  align-items: center;
}

.log-header {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-subtle);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.log-row {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-hairline);
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.log-row:last-child {
  border-bottom: none;
}

.log-col-assigned {
  color: var(--color-semantic-success);
  font-weight: 500;
}

.log-col-failed {
  color: var(--color-semantic-error);
  font-weight: 500;
}

/* 响应式 */
@media (max-width: 900px) {
  .table-header {
    display: none;
  }
  .student-table .table-row,
  .teacher-table .table-row {
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-xs) var(--spacing-sm);
    padding: var(--spacing-md);
    border: 1px solid var(--color-hairline);
    border-radius: var(--rounded-md);
    margin-bottom: var(--spacing-sm);
  }
  .col-action,
  .col-quota {
    grid-column: 1 / -1;
  }
  .student-summary {
    grid-template-columns: 1fr;
  }
}
</style>
