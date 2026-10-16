<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAdminStore } from '@/stores/admin'
import { AccountStatus } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ExcelImportButton from '@/components/base/ExcelImportButton.vue'
import { Close } from '@element-plus/icons-vue'

const adminStore = useAdminStore()
const router = useRouter()

/* ========== 搜索与筛选 ========== */
const searchKeyword = ref('')
const departmentFilter = ref<string>('ALL')

/* 院系选项 — 从学生列表中提取 */
const departmentOptions = computed(() => {
  const set = new Set<string>()
  adminStore.students.forEach((s) => set.add(s.department))
  return Array.from(set)
})

/* 过滤后的学生列表 — 按姓名/学号搜索 + 院系筛选 */
const filteredStudents = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  return adminStore.students.filter((s) => {
    const matchKeyword =
      !kw ||
      s.name.toLowerCase().includes(kw) ||
      s.studentId.toLowerCase().includes(kw)
    const matchDept =
      departmentFilter.value === 'ALL' || s.department === departmentFilter.value
    return matchKeyword && matchDept
  })
})

/* 判断学生是否有关联申请（R5-03） */
function hasApplications(studentId: number): boolean {
  return adminStore.applications.some((a) => a.studentId === studentId)
}

/* 状态徽章映射 */
function getStatusBadge(status: AccountStatus) {
  return status === AccountStatus.ACTIVE
    ? { variant: 'success' as const, label: '启用' }
    : { variant: 'default' as const, label: '禁用' }
}

/* ========== 新增/编辑弹窗 ========== */
interface StudentForm {
  studentId: string
  name: string
  major: string
  grade: string
  department: string
  phone: string
  username: string
  /* v2 创建学生时 password 必填；编辑时不修改密码 */
  password: string
}

function emptyForm(): StudentForm {
  return {
    studentId: '',
    name: '',
    major: '',
    grade: '',
    department: '',
    phone: '',
    username: '',
    password: '',
  }
}

const modalVisible = ref(false)
const isEditMode = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<StudentForm>(emptyForm())

/* ========== 表单实时验证（blur 时触发，与后端 Serializer 规则一致） ========== */
const errors = reactive<Record<string, string>>({
  studentId: '',
  name: '',
  major: '',
  grade: '',
  department: '',
  phone: '',
  username: '',
  password: '',
})

function validateField(field: keyof typeof errors): string {
  const value = (form as Record<string, string>)[field]?.trim() ?? ''
  switch (field) {
    case 'studentId':
      if (!value) return '请输入学号'
      if (!/^[a-zA-Z0-9]{6,20}$/.test(value)) return '学号只能包含字母和数字，长度6-20位'
      return ''
    case 'name':
      if (!value) return '请输入姓名'
      return ''
    case 'major':
      if (!value) return '请输入专业'
      return ''
    case 'grade':
      if (!value) return '请输入年级'
      return ''
    case 'department':
      /* 非必填：空值不报错 */
      return ''
    case 'phone':
      /* 非必填：空值不报错，有值时验证格式 */
      if (value && !/^1[3-9]\d{9}$/.test(value)) return '手机号格式不正确（应为11位数字，1开头）'
      return ''
    case 'username':
      if (!value) return '请输入用户名'
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(value)) return '用户名只能包含字母、数字、下划线，长度3-20位'
      return ''
    case 'password':
      if (isEditMode.value) return ''
      if (!value) return '请输入初始密码'
      if (value.length < 8) return '密码长度至少8位'
      return ''
  }
  return ''
}

function onFieldBlur(field: keyof typeof errors) {
  errors[field] = validateField(field)
}

function clearFieldError(field: keyof typeof errors) {
  errors[field] = ''
}

function clearAllErrors() {
  for (const key of Object.keys(errors)) {
    errors[key] = ''
  }
}

function openAddModal() {
  isEditMode.value = false
  editingId.value = null
  Object.assign(form, emptyForm())
  clearAllErrors()
  modalVisible.value = true
}

function openEditModal(id: number) {
  const target = adminStore.students.find((s) => s.id === id)
  if (!target) return
  isEditMode.value = true
  editingId.value = id
  Object.assign(form, {
    studentId: target.studentId,
    name: target.name,
    major: target.major,
    grade: target.grade,
    department: target.department,
    phone: target.phone,
    username: target.username,
    /* 编辑模式下不修改密码，重置为空 */
    password: '',
  })
  clearAllErrors()
  modalVisible.value = true
}

function closeModal() {
  modalVisible.value = false
}

function validateForm(): boolean {
  let hasError = false
  for (const field of Object.keys(errors) as (keyof typeof errors)[]) {
    const err = validateField(field)
    errors[field] = err
    if (err) hasError = true
  }
  return !hasError
}

async function handleSubmit() {
  if (!validateForm()) return
  /* R6-02~R6-04：管理员可修改学生的学号/姓名/专业等所有字段 */
  if (isEditMode.value && editingId.value !== null) {
    await adminStore.updateStudent(editingId.value, {
      studentId: form.studentId.trim(),
      name: form.name.trim(),
      major: form.major.trim(),
      grade: form.grade.trim(),
      department: form.department.trim(),
      phone: form.phone.trim(),
      username: form.username.trim(),
    })
  } else {
    const result = await adminStore.addStudent({
      studentId: form.studentId.trim(),
      name: form.name.trim(),
      major: form.major.trim(),
      grade: form.grade.trim(),
      department: form.department.trim(),
      phone: form.phone.trim(),
      username: form.username.trim(),
      password: form.password.trim(),
    })
    if (result.success && result.generatedPassword) {
      ElMessageBox.alert(
        `初始密码：${result.generatedPassword}`,
        '学生创建成功',
        { confirmButtonText: '已知晓' },
      )
    } else if (result.success) {
      alert('学生创建成功')
    }
  }
  modalVisible.value = false
}

/* ========== 删除（R5-03） ========== */
async function handleDelete(id: number) {
  const student = adminStore.students.find((s) => s.id === id)
  if (!student) return
  /* R5-03：有关联业务数据的账号只能禁用，不能物理删除 */
  if (hasApplications(id)) {
    try {
      await ElMessageBox.confirm(
        `学生「${student.name}」已关联申请记录，无法物理删除。是否改为禁用该账号？`,
        '操作确认',
        { confirmButtonText: '是，禁用账号', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
    await adminStore.toggleStudentStatus(id, AccountStatus.DISABLED)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除学生「${student.name}」？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await adminStore.deleteStudent(id)
}

/* ========== 启用/禁用 ========== */
async function handleToggleStatus(id: number) {
  const student = adminStore.students.find((s) => s.id === id)
  if (!student) return
  const next =
    student.status === AccountStatus.ACTIVE
      ? AccountStatus.DISABLED
      : AccountStatus.ACTIVE
  const action = next === AccountStatus.DISABLED ? '禁用' : '启用'
  if (!confirm(`确认${action}学生「${student.name}」的账号？`)) return
  await adminStore.toggleStudentStatus(id, next)
}

/* ========== Excel 导入入口 ========== */
function goToExcelImport() {
  router.push('/admin/excel-import?role=STUDENT')
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">学生管理</h1>
    <p class="page-description">学生账号管理</p>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchKeyword"
          class="search-input"
          placeholder="按姓名或学号搜索"
          clearable
        />
        <el-select
          v-model="departmentFilter"
          placeholder="全部院系"
          clearable
          @clear="departmentFilter = 'ALL'"
        >
          <el-option label="全部院系" value="ALL" />
          <el-option v-for="d in departmentOptions" :key="d" :label="d" :value="d" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <AppButton variant="primary" @click="openAddModal">新增学生</AppButton>
        <ExcelImportButton label="Excel 导入" @click="goToExcelImport" />
      </div>
    </div>

    <!-- 学生表格 -->
    <section class="section">
      <AppCard variant="default">
        <div v-if="filteredStudents.length" class="student-table">
          <div class="table-header">
            <div class="col-id">学号</div>
            <div class="col-name">姓名</div>
            <div class="col-major">专业</div>
            <div class="col-grade">年级</div>
            <div class="col-dept">院系</div>
            <div class="col-phone">电话</div>
            <div class="col-status">状态</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="s in filteredStudents" :key="s.id" class="table-row">
            <div class="col-id">{{ s.studentId }}</div>
            <div class="col-name">{{ s.name }}</div>
            <div class="col-major">{{ s.major }}</div>
            <div class="col-grade">{{ s.grade }}</div>
            <div class="col-dept">{{ s.department }}</div>
            <div class="col-phone">{{ s.phone }}</div>
            <div class="col-status">
              <StatusBadge
                :variant="getStatusBadge(s.status).variant"
                :label="getStatusBadge(s.status).label"
              />
            </div>
            <div class="col-action">
              <AppButton variant="tertiary" @click="openEditModal(s.id)">编辑</AppButton>
              <AppButton
                v-if="s.status === AccountStatus.ACTIVE"
                variant="secondary"
                @click="handleToggleStatus(s.id)"
              >
                禁用
              </AppButton>
              <AppButton v-else variant="primary" @click="handleToggleStatus(s.id)">
                启用
              </AppButton>
              <AppButton variant="danger" @click="handleDelete(s.id)">删除</AppButton>
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无学生记录"
          description="点击右上角「新增学生」或「批量导入」开始添加"
        />
      </AppCard>
    </section>

    <!-- 新增/编辑弹窗 -->
    <Teleport to="body">
      <div v-if="modalVisible" class="dialog-overlay" @click="closeModal">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">{{ isEditMode ? '编辑学生' : '新增学生' }}</h2>
            <el-icon class="close-btn" @click="closeModal"><Close /></el-icon>
          </div>
          <form class="dialog-body" @submit.prevent="handleSubmit">
            <div class="form-grid">
              <div class="form-field">
                <label class="form-label">学号 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.studentId"
                  placeholder="请输入学号"
                  @blur="onFieldBlur('studentId')"
                  @input="clearFieldError('studentId')"
                />
                <span v-if="errors.studentId" class="field-error">{{ errors.studentId }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">姓名 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.name"
                  placeholder="请输入姓名"
                  @blur="onFieldBlur('name')"
                  @input="clearFieldError('name')"
                />
                <span v-if="errors.name" class="field-error">{{ errors.name }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">专业 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.major"
                  placeholder="请输入专业"
                  @blur="onFieldBlur('major')"
                  @input="clearFieldError('major')"
                />
                <span v-if="errors.major" class="field-error">{{ errors.major }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">年级 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.grade"
                  placeholder="请输入年级"
                  @blur="onFieldBlur('grade')"
                  @input="clearFieldError('grade')"
                />
                <span v-if="errors.grade" class="field-error">{{ errors.grade }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">院系</label>
                <el-input
                  v-model="form.department"
                  placeholder="请输入院系"
                  @blur="onFieldBlur('department')"
                  @input="clearFieldError('department')"
                />
                <span v-if="errors.department" class="field-error">{{ errors.department }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">电话</label>
                <el-input
                  v-model="form.phone"
                  placeholder="请输入电话"
                  @blur="onFieldBlur('phone')"
                  @input="clearFieldError('phone')"
                />
                <span v-if="errors.phone" class="field-error">{{ errors.phone }}</span>
              </div>
              <div class="form-field form-field-full">
                <label class="form-label">用户名（登录账号） <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.username"
                  placeholder="请输入用户名"
                  @blur="onFieldBlur('username')"
                  @input="clearFieldError('username')"
                />
                <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
              </div>
              <!-- v2 创建学生时 password 必填；编辑时不显示 -->
              <div v-if="!isEditMode" class="form-field form-field-full">
                <label class="form-label">初始密码 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.password"
                  type="password"
                  placeholder="请输入初始密码"
                  show-password
                  @blur="onFieldBlur('password')"
                  @input="clearFieldError('password')"
                />
                <span v-if="errors.password" class="field-error">{{ errors.password }}</span>
              </div>
            </div>
            <div class="dialog-footer">
              <AppButton type="button" variant="tertiary" @click="closeModal">取消</AppButton>
              <AppButton type="submit" variant="primary">
                {{ isEditMode ? '保存' : '新增' }}
              </AppButton>
            </div>
          </form>
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

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex: 1;
  min-width: 240px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.search-input {
  flex: 1;
  min-width: 200px;
}

/* Section */
.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* 表格 — CSS Grid */
.student-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr 0.8fr 1.2fr 1.2fr 0.9fr 1.9fr;
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

.col-id {
  font-family: var(--font-mono);
  font-size: var(--text-mono);
  color: var(--color-ink-muted);
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
  width: 560px;
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

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-field-full {
  grid-column: 1 / -1;
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

.form-input {
  background: var(--color-surface-1);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  padding: var(--spacing-xs) var(--spacing-sm);
  color: var(--color-ink);
  font-size: var(--text-body);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.form-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.form-input::placeholder {
  color: var(--color-ink-subtle);
}

.import-hint {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
  white-space: pre-wrap;
  background: var(--color-surface-2);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  padding: var(--spacing-sm) var(--spacing-md);
  line-height: var(--text-body-sm-line);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-top: var(--spacing-md);
}

/* 响应式 */
@media (max-width: 900px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-left {
    flex-direction: column;
    align-items: stretch;
  }
  .toolbar-right {
    justify-content: flex-end;
  }
  .table-header {
    display: none;
  }
  .table-row {
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-xs) var(--spacing-sm);
    padding: var(--spacing-md);
    border: 1px solid var(--color-hairline);
    border-radius: var(--rounded-md);
    margin-bottom: var(--spacing-sm);
  }
  .col-action {
    grid-column: 1 / -1;
  }
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
