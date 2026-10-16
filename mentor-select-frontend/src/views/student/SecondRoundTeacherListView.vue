<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import type { TeacherInfo } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import TeacherDetailDialog from '@/components/base/TeacherDetailDialog.vue'

const studentStore = useStudentStore()
const router = useRouter()

/* 资格检查：仅第一轮被拒学生可参加第二轮 */
const canAccess = computed(() => studentStore.isRejectedInRound1)
const hasSecondRoundApplication = computed(() => !!studentStore.mySecondRoundApplication)
const isSubmitting = ref(false)

/* 搜索词 — 按姓名搜索 */
const searchKeyword = ref('')

/* 学院筛选条件 */
const selectedDepartment = ref('')

/* 选中的导师（用于详情弹窗） */
const selectedTeacher = ref<TeacherInfo | null>(null)

/* 通知消息（成功 / 失败提示） */
interface ToastMessage {
  type: 'success' | 'error'
  text: string
}
const toast = ref<ToastMessage | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(type: 'success' | 'error', text: string) {
  if (toastTimer) {
    clearTimeout(toastTimer)
  }
  toast.value = { type, text }
  toastTimer = setTimeout(() => {
    toast.value = null
  }, 3000)
}

/* 学院列表 — 从导师数据中提取去重 */
const departments = computed(() => {
  const set = new Set<string>()
  studentStore.teachers.forEach((t) => set.add(t.department))
  return Array.from(set)
})

/* 过滤后的导师列表 */
const filteredTeachers = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  const dept = selectedDepartment.value
  return studentStore.teachers.filter((t) => {
    const matchName = keyword ? t.name.toLowerCase().includes(keyword) : true
    const matchDept = dept ? t.department === dept : true
    return matchName && matchDept
  })
})

/* 名额是否已满 */
function isQuotaFull(teacher: TeacherInfo): boolean {
  return teacher.maxQuota - teacher.currentAdmitted <= 0
}

/* 打开导师详情弹窗 */
function openDetail(teacher: TeacherInfo) {
  selectedTeacher.value = teacher
}

/* 关闭弹窗 */
function closeDetail() {
  selectedTeacher.value = null
}

/* 提交第二轮申请 */
async function handleApply(teacherId: number) {
  if (isSubmitting.value || hasSecondRoundApplication.value) return
  isSubmitting.value = true
  try {
    const result = await studentStore.submitSecondRoundApplication(teacherId)
    if (result.success) {
      showToast('success', result.message)
      selectedTeacher.value = null
      await router.push('/student/second-round/my')
    } else {
      showToast('error', result.message)
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">二轮导师列表</h1>
    <p class="page-description">先到先得选择有余额的导师</p>

    <!-- 资格提示：非第一轮被拒学生不可参加第二轮 -->
    <AppCard v-if="!canAccess" variant="default">
      <p class="access-denied">仅第一轮未录取学生可参加第二轮</p>
    </AppCard>

    <template v-else>
      <!-- 通知提示 -->
      <transition name="toast">
        <div
          v-if="toast"
          :class="['toast', `toast-${toast.type}`]"
          role="status"
        >
          {{ toast.text }}
        </div>
      </transition>

      <!-- 搜索 + 筛选 -->
      <div class="toolbar">
        <div class="search-field">
          <label class="field-label" for="teacher-search">搜索导师</label>
          <el-input
            id="teacher-search"
            v-model="searchKeyword"
            class="search-input"
            placeholder="按姓名搜索"
            clearable
          />
        </div>
        <div class="filter-field">
          <label class="field-label" for="department-filter">学院筛选</label>
          <el-select
            id="department-filter"
            v-model="selectedDepartment"
            class="filter-select"
          >
            <el-option label="全部学院" value="" />
            <el-option v-for="dept in departments" :key="dept" :label="dept" :value="dept" />
          </el-select>
        </div>
      </div>

      <!-- 导师卡片列表 -->
      <div v-if="filteredTeachers.length" class="teacher-grid">
        <AppCard
          v-for="teacher in filteredTeachers"
          :key="teacher.id"
          variant="default"
          class="teacher-card"
        >
          <div class="card-header" @click="openDetail(teacher)">
            <div class="header-left">
              <h3 class="teacher-name">{{ teacher.name }}</h3>
              <span class="teacher-title">{{ teacher.title }}</span>
            </div>
            <span class="teacher-dept">{{ teacher.department }}</span>
          </div>

          <div class="card-body" @click="openDetail(teacher)">
            <div class="info-row">
              <span class="info-key">研究方向</span>
              <span class="info-val">{{ teacher.researchArea }}</span>
            </div>
            <div class="quota-row">
              <QuotaBadge
                :admitted="teacher.currentAdmitted"
                :max="teacher.maxQuota"
              />
            </div>
          </div>

          <div class="card-footer">
            <AppButton
              variant="primary"
              :disabled="isQuotaFull(teacher) || hasSecondRoundApplication || isSubmitting"
              @click="handleApply(teacher.id)"
            >
              {{ hasSecondRoundApplication ? '已提交二轮申请' : isQuotaFull(teacher) ? '名额已满' : '申请' }}
            </AppButton>
          </div>
        </AppCard>
      </div>

      <!-- 空状态 -->
      <EmptyState
        v-else
        title="未找到匹配的导师"
        description="请尝试调整搜索或筛选条件"
      />

      <!-- 导师详情弹窗 -->
      <TeacherDetailDialog
        v-if="selectedTeacher"
        :teacher="selectedTeacher"
        :show-apply-button="true"
        :apply-disabled="isQuotaFull(selectedTeacher) || hasSecondRoundApplication || isSubmitting"
        :apply-button-text="hasSecondRoundApplication ? '已提交二轮申请' : isQuotaFull(selectedTeacher) ? '名额已满' : '申请'"
        @close="closeDetail"
        @apply="handleApply"
      />
    </template>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 960px;
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

/* 资格拒绝提示 */
.access-denied {
  font-size: var(--text-body);
  color: var(--color-ink-muted);
  text-align: center;
  padding: var(--spacing-md);
}

/* 通知 toast */
.toast {
  font-size: var(--text-body-sm);
  border-radius: var(--rounded-md);
  padding: var(--spacing-sm) var(--spacing-md);
  margin-bottom: var(--spacing-md);
  border: 1px solid;
}

.toast-success {
  background: var(--color-success-bg);
  color: var(--color-semantic-success);
  border-color: var(--color-success-border);
}

.toast-error {
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
  border-color: var(--color-error-border);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* 工具栏：搜索 + 筛选 */
.toolbar {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.search-field,
.filter-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.field-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.search-input,
.filter-select {
  width: 100%;
}

/* 导师卡片网格 — 桌面 2 列 */
.teacher-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
  align-items: start;
}

.teacher-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.card-header,
.card-body {
  cursor: pointer;
  transition: color 0.15s;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--color-hairline);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.teacher-name {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.teacher-title {
  font-size: var(--text-caption);
  color: var(--color-ink-muted);
  background: var(--color-surface-3);
  border-radius: var(--rounded-pill);
  padding: 2px var(--spacing-xs);
}

.teacher-dept {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-key {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-val {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.quota-row {
  display: flex;
  align-items: center;
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
}

/* 响应式：移动端单列 */
@media (max-width: 768px) {
  .toolbar {
    grid-template-columns: 1fr;
  }

  .teacher-grid {
    grid-template-columns: 1fr;
  }
}
</style>
