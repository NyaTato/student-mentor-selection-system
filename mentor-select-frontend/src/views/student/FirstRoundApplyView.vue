<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStudentStore } from '@/stores/student'
import type { TeacherInfo } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'

const studentStore = useStudentStore()
const route = useRoute()
const router = useRouter()

/* 当前学生已有第一轮申请 */
const existingApplication = computed(() => studentStore.myFirstRoundApplication)

/* 已选导师详情（用于顶部展示） */
const existingTeacher = computed<TeacherInfo | undefined>(() => {
  const app = existingApplication.value
  if (!app) return undefined
  return studentStore.getTeacherById(app.teacherId)
})

/* 当前选中的导师 id — 单选 */
const selectedTeacherId = ref<number | null>(null)

/* 按钮文案：已有申请为"修改志愿"，否则为"提交志愿" */
const buttonText = computed(() =>
  existingApplication.value ? '修改志愿' : '提交志愿',
)

/* 初始化预选：已有申请则预选已选导师；否则读取 query.teacherId 预选 */
function initSelection() {
  if (existingApplication.value) {
    selectedTeacherId.value = existingApplication.value.teacherId
    return
  }
  const fromQuery = route.query.teacherId
  if (typeof fromQuery === 'string' && fromQuery) {
    const id = Number(fromQuery)
    if (!Number.isNaN(id)) {
      selectedTeacherId.value = id
    }
  }
}

initSelection()

function selectTeacher(teacherId: number) {
  selectedTeacherId.value = teacherId
}

/* 提交 / 修改志愿 — 成功后跳转 Dashboard */
async function handleSubmit() {
  if (selectedTeacherId.value === null) return
  try {
    await studentStore.submitFirstRoundApplication(selectedTeacherId.value)
    router.push('/student/dashboard')
  } catch {
    /* 错误已由 http 拦截器提示 */
  }
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">填报志愿</h1>
    <p class="page-description">选择并提交第一轮导师申请</p>

    <!-- 规则提示 -->
    <div class="tip-banner">
      本轮仅可选择一名导师，提交后截止前可修改
    </div>

    <!-- 已有申请：展示当前已选导师 -->
    <AppCard
      v-if="existingApplication && existingTeacher"
      variant="compact"
      class="current-card"
    >
      <div class="current-row">
        <span class="current-label">当前已选导师</span>
        <span class="current-name">{{ existingTeacher.name }}</span>
        <span class="current-meta">
          {{ existingTeacher.department }} · {{ existingTeacher.title }}
        </span>
      </div>
    </AppCard>

    <!-- 导师选择列表 -->
    <section class="section">
      <h2 class="section-title">选择导师</h2>
      <div v-if="studentStore.teachers.length" class="teacher-list">
        <div
          v-for="teacher in studentStore.teachers"
          :key="teacher.id"
          :class="[
            'teacher-option',
            { 'teacher-option-selected': selectedTeacherId === teacher.id },
          ]"
          @click="selectTeacher(teacher.id)"
        >
          <div class="option-main">
            <div class="option-header">
              <span
                class="radio"
                :class="{ 'radio-checked': selectedTeacherId === teacher.id }"
              ></span>
              <span class="option-name">{{ teacher.name }}</span>
              <span class="option-title">{{ teacher.title }}</span>
            </div>
            <div class="option-meta">{{ teacher.department }}</div>
            <div class="option-area">研究方向：{{ teacher.researchArea }}</div>
          </div>
          <div class="option-quota">
            <span class="quota-key">招生名额</span>
            <span class="quota-val">{{ teacher.maxQuota }} 人</span>
          </div>
        </div>
      </div>
      <p v-else class="empty-text">暂无可选导师</p>
    </section>

    <!-- 底部提交按钮 -->
    <div class="footer-actions">
      <AppButton
        variant="primary"
        :disabled="selectedTeacherId === null"
        @click="handleSubmit"
      >
        {{ buttonText }}
      </AppButton>
    </div>
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

/* 规则提示横幅 */
.tip-banner {
  font-size: var(--text-body-sm);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--rounded-md);
  padding: var(--spacing-sm) var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

/* 当前已选导师卡片 */
.current-card {
  margin-bottom: var(--spacing-lg);
}

.current-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-sm);
}

.current-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
  letter-spacing: var(--text-eyebrow-spacing);
}

.current-name {
  font-size: var(--text-body);
  color: var(--color-ink);
  font-weight: 500;
}

.current-meta {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

/* 选择列表区 */
.section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.teacher-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* 单选卡片 */
.teacher-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-md);
  background: var(--color-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-lg);
  padding: var(--spacing-md);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.teacher-option:hover {
  border-color: var(--color-primary-border);
}

.teacher-option-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.option-main {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex: 1;
  min-width: 0;
}

.option-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

/* 自定义单选圆点 */
.radio {
  width: 16px;
  height: 16px;
  border-radius: var(--rounded-full);
  border: 2px solid var(--color-hairline-strong);
  background: var(--color-card);
  flex-shrink: 0;
  transition: border-color 0.15s, background 0.15s;
}

.radio-checked {
  border-color: var(--color-primary);
  background: var(--color-primary);
  box-shadow: inset 0 0 0 3px var(--color-card);
}

.option-name {
  font-size: var(--text-body);
  font-weight: 500;
  color: var(--color-ink);
}

.option-title {
  font-size: var(--text-caption);
  color: var(--color-ink-muted);
  background: var(--color-surface-3);
  border-radius: var(--rounded-pill);
  padding: 2px var(--spacing-xs);
}

.option-meta {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

.option-area {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.option-quota {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
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

.empty-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
  text-align: center;
  padding: var(--spacing-lg);
}

/* 底部操作 */
.footer-actions {
  display: flex;
  justify-content: flex-start;
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
}

/* 响应式：窄屏堆叠 */
@media (max-width: 600px) {
  .teacher-option {
    flex-direction: column;
    align-items: flex-start;
  }

  .option-quota {
    align-items: flex-start;
  }
}
</style>
