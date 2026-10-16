<script setup lang="ts">
import { ref, computed } from 'vue'
import { useStudentStore } from '@/stores/student'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'

const studentStore = useStudentStore()

/* 当前学生 — 学号、姓名、专业、年级、院系为只读，手机号可修改 */
const student = computed(() => studentStore.currentStudent)

const phone = ref(student.value.phone)
const saveSuccess = ref(false)
const phoneError = ref('')

/* 手机号格式验证（与后端 Serializer 规则一致） */
function validatePhone(): string {
  const v = phone.value.trim()
  if (!v) return '请输入手机号'
  if (!/^1[3-9]\d{9}$/.test(v)) return '手机号格式不正确（应为11位数字，1开头）'
  return ''
}

function onPhoneBlur() {
  phoneError.value = validatePhone()
}

function clearPhoneError() {
  phoneError.value = ''
}

async function handleSave() {
  phoneError.value = validatePhone()
  if (phoneError.value) return
  try {
    await studentStore.updatePhone(phone.value)
    saveSuccess.value = true
    window.setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch {
    /* 错误消息由全局拦截器显示 */
  }
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">个人信息</h1>
    <p class="page-description">查看和修改个人信息</p>

    <AppCard variant="default">
      <form class="info-form" @submit.prevent="handleSave">
        <div class="form-grid">
          <!-- 只读字段：学号 -->
          <div class="form-field">
            <label class="form-label">学号</label>
            <el-input :model-value="student.studentId" readonly disabled />
          </div>

          <!-- 只读字段：姓名 -->
          <div class="form-field">
            <label class="form-label">姓名</label>
            <el-input :model-value="student.name" readonly disabled />
          </div>

          <!-- 只读字段：专业 -->
          <div class="form-field">
            <label class="form-label">专业</label>
            <el-input :model-value="student.major" readonly disabled />
          </div>

          <!-- 只读字段：年级 -->
          <div class="form-field">
            <label class="form-label">年级</label>
            <el-input :model-value="student.grade" readonly disabled />
          </div>

          <!-- 只读字段：院系 -->
          <div class="form-field">
            <label class="form-label">院系</label>
            <el-input :model-value="student.department" readonly disabled />
          </div>

          <!-- 可修改字段：手机号 -->
          <div class="form-field">
            <label class="form-label">手机号 <span style="color: var(--color-semantic-error)">*</span></label>
            <el-input
              v-model="phone"
              type="tel"
              placeholder="请输入手机号"
              @blur="onPhoneBlur"
              @input="clearPhoneError"
            />
            <span v-if="phoneError" class="field-error">{{ phoneError }}</span>
          </div>
        </div>

        <p v-if="saveSuccess" class="form-success">保存成功</p>

        <div class="form-actions">
          <AppButton type="submit" variant="primary">保存</AppButton>
        </div>
      </form>
    </AppCard>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 720px;
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

.info-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.field-error {
  display: block;
  margin-top: 4px;
  font-size: var(--text-caption);
  color: var(--color-semantic-error);
  line-height: 1.4;
}

/* 保存成功提示 */
.form-success {
  font-size: var(--text-body-sm);
  color: var(--color-semantic-success);
  background: var(--color-success-bg);
  border: 1px solid var(--color-success-border);
  border-radius: var(--rounded-md);
  padding: var(--spacing-xs) var(--spacing-sm);
}

.form-actions {
  display: flex;
  justify-content: flex-start;
}

/* 响应式：窄屏单列 */
@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
