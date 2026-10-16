<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useTeacherStore } from '@/stores/teacher'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'

const teacherStore = useTeacherStore()

const teacher = computed(() => teacherStore.currentTeacher)

/* 编辑模式 */
const isEditing = ref(false)

/* 编辑表单 */
const form = reactive({
  researchArea: '',
  profile: '',
  projectDirection: '',
  researchTopics: '',
  requirements: '',
})

/* 进入编辑模式 */
function startEdit() {
  form.researchArea = teacher.value.researchArea
  form.profile = teacher.value.profile
  form.projectDirection = teacher.value.projectDirection
  form.researchTopics = teacher.value.researchTopics
  form.requirements = teacher.value.requirements
  isEditing.value = true
}

/* 取消编辑 */
function cancelEdit() {
  isEditing.value = false
}

/* 保存修改 */
function saveEdit() {
  if (!form.researchArea.trim()) {
    alert('研究方向不能为空')
    return
  }
  teacherStore.updateProfile({
    researchArea: form.researchArea,
    profile: form.profile,
    projectDirection: form.projectDirection,
    researchTopics: form.researchTopics,
    requirements: form.requirements,
  })
  isEditing.value = false
}

/* 只读字段 */
const readonlyFields = computed(() => ({
  name: teacher.value.name,
  username: teacher.value.username,
  department: teacher.value.department,
  title: teacher.value.title,
  maxQuota: teacher.value.maxQuota,
  currentAdmitted: teacher.value.currentAdmitted,
}))
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">个人信息</h1>
    <p class="page-description">查看和修改导师个人信息</p>

    <!-- 只读信息 -->
    <section class="section">
      <h2 class="section-title">基础信息（只读）</h2>
      <AppCard variant="default">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">姓名</span>
            <span class="info-value">{{ readonlyFields.name }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">用户名</span>
            <span class="info-value">{{ readonlyFields.username }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">院系</span>
            <span class="info-value">{{ readonlyFields.department }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">职称</span>
            <span class="info-value">{{ readonlyFields.title }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">招生名额</span>
            <span class="info-value">{{ readonlyFields.maxQuota }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">已录取</span>
            <span class="info-value">{{ readonlyFields.currentAdmitted }}</span>
          </div>
        </div>
      </AppCard>
    </section>

    <!-- 可编辑信息 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">招生信息</h2>
        <div v-if="!isEditing" class="section-actions">
          <AppButton variant="primary" @click="startEdit">编辑</AppButton>
        </div>
        <div v-else class="section-actions">
          <AppButton variant="secondary" @click="cancelEdit">取消</AppButton>
          <AppButton variant="primary" @click="saveEdit">保存</AppButton>
        </div>
      </div>

      <AppCard variant="default">
        <!-- 查看模式 -->
        <div v-if="!isEditing" class="view-mode">
          <div class="field-group">
            <label class="field-label">研究方向</label>
            <p class="field-value">{{ teacher.researchArea }}</p>
          </div>
          <div class="field-group">
            <label class="field-label">个人简介</label>
            <p class="field-value field-value-text">{{ teacher.profile }}</p>
          </div>
          <div class="field-group">
            <label class="field-label">指导方向</label>
            <p class="field-value field-value-text">{{ teacher.projectDirection }}</p>
          </div>
          <div class="field-group">
            <label class="field-label">课题题目</label>
            <p class="field-value field-value-text field-value-pre">{{ teacher.researchTopics }}</p>
          </div>
          <div class="field-group">
            <label class="field-label">对学生的要求</label>
            <p class="field-value field-value-text">{{ teacher.requirements }}</p>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-else class="edit-mode">
          <div class="form-group">
            <label class="form-label">研究方向 <span class="required">*</span></label>
            <el-input
              v-model="form.researchArea"
              placeholder="请输入研究方向"
            />
          </div>
          <div class="form-group">
            <label class="form-label">个人简介</label>
            <el-input
              v-model="form.profile"
              type="textarea"
              :rows="4"
              placeholder="请输入个人简介"
            />
          </div>
          <div class="form-group">
            <label class="form-label">指导方向</label>
            <el-input
              v-model="form.projectDirection"
              type="textarea"
              :rows="3"
              placeholder="请输入指导方向"
            />
          </div>
          <div class="form-group">
            <label class="form-label">课题题目</label>
            <el-input
              v-model="form.researchTopics"
              type="textarea"
              :rows="4"
              placeholder="每行一个课题题目"
            />
          </div>
          <div class="form-group">
            <label class="form-label">对学生的要求</label>
            <el-input
              v-model="form.requirements"
              type="textarea"
              :rows="3"
              placeholder="请输入对学生的要求"
            />
          </div>
        </div>
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 900px;
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

.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

/* 基础信息 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.info-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-value {
  font-size: var(--text-body);
  color: var(--color-ink);
  font-weight: 500;
}

/* 查看模式 */
.view-mode {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.field-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
  font-weight: 500;
}

.field-value {
  font-size: var(--text-body);
  color: var(--color-ink);
  line-height: 1.6;
}

.field-value-text {
  white-space: pre-wrap;
}

.field-value-pre {
  font-family: var(--font-mono, inherit);
  background: var(--color-surface-2);
  padding: var(--spacing-sm);
  border-radius: var(--rounded-md);
}

/* 编辑模式 */
.edit-mode {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xxs);
}

.form-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.required {
  color: var(--color-semantic-error);
}
</style>
