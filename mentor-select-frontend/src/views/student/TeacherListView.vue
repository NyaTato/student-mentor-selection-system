<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import type { TeacherInfo } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import TeacherDetailDialog from '@/components/base/TeacherDetailDialog.vue'

const studentStore = useStudentStore()
const router = useRouter()

/* 搜索词 — 按姓名搜索 */
const searchKeyword = ref('')

/* 学院筛选条件 */
const selectedDepartment = ref('')

/* 选中的导师（用于详情弹窗） */
const selectedTeacher = ref<TeacherInfo | null>(null)

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

/* 打开导师详情弹窗 */
function openDetail(teacher: TeacherInfo) {
  selectedTeacher.value = teacher
}

/* 关闭弹窗 */
function closeDetail() {
  selectedTeacher.value = null
}

/* 弹窗内"选择导师"按钮 — 跳转志愿填报页并传递 teacherId */
function handleApply(teacherId: number) {
  selectedTeacher.value = null
  router.push({
    path: '/student/first-round/apply',
    query: { teacherId: String(teacherId) },
  })
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">导师列表</h1>
    <p class="page-description">浏览导师信息并选择导师</p>

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
        @click="openDetail(teacher)"
      >
        <div class="card-header">
          <div class="header-left">
            <h3 class="teacher-name">{{ teacher.name }}</h3>
            <span class="teacher-title">{{ teacher.title }}</span>
          </div>
          <span class="teacher-dept">{{ teacher.department }}</span>
        </div>

        <div class="card-body">
          <div class="info-row">
            <span class="info-key">研究方向</span>
            <span class="info-val">{{ teacher.researchArea }}</span>
          </div>
          <div class="quota-row">
            <div class="quota-item">
              <span class="quota-key">招生名额</span>
              <span class="quota-val">{{ teacher.maxQuota }} 人</span>
            </div>
            <div class="quota-item">
              <span class="quota-key">当前申请人数</span>
              <span class="quota-val">{{ teacher.currentAdmitted }} 人</span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <span class="view-detail">查看详情 →</span>
        </div>
      </AppCard>
    </div>

    <!-- 空状态 -->
    <p v-else class="empty-text">未找到匹配的导师</p>

    <!-- 导师详情弹窗 -->
    <TeacherDetailDialog
      v-if="selectedTeacher"
      :teacher="selectedTeacher"
      :show-apply-button="true"
      apply-button-text="选择导师"
      @close="closeDetail"
      @apply="handleApply"
    />
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
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.teacher-card:hover {
  border-color: var(--color-primary-border);
  box-shadow: var(--shadow-lg);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
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
  gap: var(--spacing-md);
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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
}

.quota-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quota-key {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.quota-val {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.card-footer {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
}

.view-detail {
  font-size: var(--text-body-sm);
  color: var(--color-primary);
  font-weight: 500;
}

.empty-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
  text-align: center;
  padding: var(--spacing-xxl);
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
