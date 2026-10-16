<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import { AccountStatus, type TeacherInfo } from '@/types'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import QuotaBadge from '@/components/base/QuotaBadge.vue'
import ExcelImportButton from '@/components/base/ExcelImportButton.vue'

/* 导师行类型 — TeacherInfo + 账号状态 */
type TeacherRow = TeacherInfo & { status: AccountStatus }

const adminStore = useAdminStore()
const router = useRouter()

/* ========== 搜索与筛选 ========== */
const searchKeyword = ref('')
const departmentFilter = ref<string>('ALL')

/* 院系选项 — 从导师列表中提取 */
const departmentOptions = computed(() => {
  const set = new Set<string>()
  adminStore.teachers.forEach((t) => set.add(t.department))
  return Array.from(set)
})

/* 过滤后的导师列表 — 按姓名/工号搜索 + 院系筛选 */
const filteredTeachers = computed<TeacherRow[]>(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  const dept = departmentFilter.value
  return adminStore.teachers.filter((t) => {
    const matchKeyword =
      !kw ||
      t.name.toLowerCase().includes(kw) ||
      t.teacherNumber.toLowerCase().includes(kw) ||
      t.username.toLowerCase().includes(kw)
    const matchDept = dept === 'ALL' || t.department === dept
    return matchKeyword && matchDept
  })
})

/* 状态徽章映射 */
function getStatusBadge(status: AccountStatus) {
  return status === AccountStatus.ACTIVE
    ? { variant: 'success' as const, label: '启用' }
    : { variant: 'default' as const, label: '禁用' }
}

/* 判断导师是否有关联申请（R5-03） */
function hasApplications(teacherId: number): boolean {
  return adminStore.applications.some((a) => a.teacherId === teacherId)
}

/* ========== 新增/编辑弹窗 ========== */
interface TeacherForm {
  username: string
  teacherNumber: string
  name: string
  department: string
  title: string
  researchArea: string
  profile: string
  maxQuota: number
  projectDirection: string
  researchTopics: string
  requirements: string
  /* v2 创建导师时 password 必填；编辑时不修改密码 */
  password: string
}

function emptyForm(): TeacherForm {
  return {
    username: '',
    teacherNumber: '',
    name: '',
    department: '',
    title: '',
    researchArea: '',
    profile: '',
    maxQuota: 0,
    projectDirection: '',
    researchTopics: '',
    requirements: '',
    password: '',
  }
}

const modalVisible = ref(false)
const isEditMode = ref(false)
const editingId = ref<number | null>(null)
const form = reactive<TeacherForm>(emptyForm())

/* ========== 表单实时验证（blur 时触发，与后端 Serializer 规则一致） ========== */
const errors = reactive<Record<string, string>>({
  username: '',
  teacherNumber: '',
  name: '',
  department: '',
  maxQuota: '',
  password: '',
})

function validateField(field: keyof typeof errors): string {
  switch (field) {
    case 'username': {
      const v = form.username.trim()
      if (!v) return '请输入登录用户名'
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(v)) return '用户名只能包含字母、数字、下划线，长度3-20位'
      return ''
    }
    case 'teacherNumber': {
      const v = form.teacherNumber.trim()
      if (!v) return '请输入工号'
      if (!/^[a-zA-Z0-9]{6,20}$/.test(v)) return '工号只能包含字母和数字，长度6-20位'
      return ''
    }
    case 'name': {
      const v = form.name.trim()
      if (!v) return '请输入姓名'
      return ''
    }
    case 'department': {
      const v = form.department.trim()
      if (!v) return '请输入院系'
      return ''
    }
    case 'maxQuota': {
      if (!Number.isFinite(form.maxQuota) || form.maxQuota < 0) return '招生名额必须为非负整数'
      return ''
    }
    case 'password': {
      if (isEditMode.value) return ''
      const v = form.password.trim()
      if (!v) return '请输入初始密码'
      if (v.length < 8) return '密码长度至少8位'
      return ''
    }
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
  const target = adminStore.teachers.find((t) => t.id === id)
  if (!target) return
  isEditMode.value = true
  editingId.value = id
  Object.assign(form, {
    username: target.username,
    teacherNumber: target.teacherNumber,
    name: target.name,
    department: target.department,
    title: target.title,
    researchArea: target.researchArea,
    profile: target.profile,
    maxQuota: target.maxQuota,
    projectDirection: target.projectDirection,
    researchTopics: target.researchTopics,
    requirements: target.requirements,
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
  if (isEditMode.value && editingId.value !== null) {
    await adminStore.updateTeacher(editingId.value, {
      username: form.username.trim(),
      teacherNumber: form.teacherNumber.trim(),
      name: form.name.trim(),
      department: form.department.trim(),
      title: form.title.trim(),
      researchArea: form.researchArea.trim(),
      profile: form.profile.trim(),
      maxQuota: form.maxQuota,
      projectDirection: form.projectDirection.trim(),
      researchTopics: form.researchTopics.trim(),
      requirements: form.requirements.trim(),
    })
    alert('修改成功')
  } else {
    const result = await adminStore.addTeacher({
      username: form.username.trim(),
      teacherNumber: form.teacherNumber.trim(),
      name: form.name.trim(),
      department: form.department.trim(),
      title: form.title.trim(),
      researchArea: form.researchArea.trim(),
      profile: form.profile.trim(),
      maxQuota: form.maxQuota,
      currentAdmitted: 0,
      projectDirection: form.projectDirection.trim(),
      researchTopics: form.researchTopics.trim(),
      requirements: form.requirements.trim(),
      password: form.password.trim(),
    })
    if (result.success && result.generatedPassword) {
      ElMessageBox.alert(
        `初始密码：${result.generatedPassword}`,
        '导师创建成功',
        { confirmButtonText: '已知晓' },
      )
    } else if (result.success) {
      alert('新增导师成功')
    }
  }
  modalVisible.value = false
}

/* ========== 设置名额弹窗 ========== */
const quotaModalVisible = ref(false)
const quotaTeacherId = ref<number | null>(null)
const quotaTeacherName = ref('')
const quotaCurrentAdmitted = ref(0)
const quotaInput = ref(0)
const quotaError = ref('')

function openQuotaModal(id: number) {
  const target = adminStore.teachers.find((t) => t.id === id)
  if (!target) return
  quotaTeacherId.value = id
  quotaTeacherName.value = target.name
  quotaCurrentAdmitted.value = target.currentAdmitted
  quotaInput.value = target.maxQuota
  quotaError.value = ''
  quotaModalVisible.value = true
}

function closeQuotaModal() {
  quotaModalVisible.value = false
  quotaTeacherId.value = null
  quotaError.value = ''
}

async function submitQuota() {
  if (quotaTeacherId.value === null) return
  if (!Number.isFinite(quotaInput.value) || quotaInput.value < 0) {
    quotaError.value = '请输入有效的非负整数'
    return
  }
  /* 校验：不能少于已录取人数 */
  if (quotaInput.value < quotaCurrentAdmitted.value) {
    quotaError.value = `名额不能少于已录取人数（${quotaCurrentAdmitted.value}）`
    return
  }
  await adminStore.setTeacherQuota(quotaTeacherId.value, quotaInput.value)
  alert('名额设置成功')
  closeQuotaModal()
}

/* ========== 启用/禁用 ========== */
async function handleToggleStatus(id: number) {
  const teacher = adminStore.teachers.find((t) => t.id === id)
  if (!teacher) return
  const next =
    teacher.status === AccountStatus.ACTIVE
      ? AccountStatus.DISABLED
      : AccountStatus.ACTIVE
  const action = next === AccountStatus.DISABLED ? '禁用' : '启用'
  if (!confirm(`确认${action}导师「${teacher.name}」的账号？`)) return
  await adminStore.toggleTeacherStatus(id, next)
  alert(`${action}成功`)
}

/* ========== 删除（R5-03） ========== */
async function handleDelete(id: number) {
  const teacher = adminStore.teachers.find((t) => t.id === id)
  if (!teacher) return
  /* R5-03：有关联业务数据的账号只能禁用，不能物理删除 */
  if (hasApplications(id)) {
    try {
      await ElMessageBox.confirm(
        `导师「${teacher.name}」已关联申请记录，无法物理删除。是否改为禁用该账号？`,
        '操作确认',
        { confirmButtonText: '是，禁用账号', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
    await adminStore.toggleTeacherStatus(id, AccountStatus.DISABLED)
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认删除导师「${teacher.name}」？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  await adminStore.deleteTeacher(id)
  alert('删除成功')
}

/* ========== Excel 导入入口 ========== */
function goToExcelImport() {
  router.push('/admin/excel-import?role=TEACHER')
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">导师管理</h1>
    <p class="page-description">导师账号和招生名额管理</p>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchKeyword"
          class="search-input"
          placeholder="按姓名或工号搜索"
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
        <AppButton variant="primary" @click="openAddModal">新增导师</AppButton>
        <ExcelImportButton label="Excel 导入" @click="goToExcelImport" />
      </div>
    </div>

    <!-- 导师表格 -->
    <section class="section">
      <AppCard variant="default">
        <div v-if="filteredTeachers.length" class="teacher-table">
          <div class="table-header">
            <div class="col-id">工号</div>
            <div class="col-name">姓名</div>
            <div class="col-dept">院系</div>
            <div class="col-title">职称</div>
            <div class="col-area">研究方向</div>
            <div class="col-quota">招生名额</div>
            <div class="col-admitted">已录取</div>
            <div class="col-status">状态</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="t in filteredTeachers" :key="t.id" class="table-row">
            <div class="col-id">{{ t.teacherNumber }}</div>
            <div class="col-name">{{ t.name }}</div>
            <div class="col-dept">{{ t.department }}</div>
            <div class="col-title">{{ t.title }}</div>
            <div class="col-area" :title="t.researchArea">{{ t.researchArea }}</div>
            <div class="col-quota">{{ t.maxQuota }}</div>
            <div class="col-admitted">{{ t.currentAdmitted }}</div>
            <div class="col-status">
              <StatusBadge
                :variant="getStatusBadge(t.status).variant"
                :label="getStatusBadge(t.status).label"
              />
            </div>
            <div class="col-action">
              <AppButton variant="tertiary" @click="openEditModal(t.id)">编辑</AppButton>
              <AppButton variant="secondary" @click="openQuotaModal(t.id)">设置名额</AppButton>
              <AppButton
                v-if="t.status === AccountStatus.ACTIVE"
                variant="secondary"
                @click="handleToggleStatus(t.id)"
              >
                禁用
              </AppButton>
              <AppButton v-else variant="primary" @click="handleToggleStatus(t.id)">
                启用
              </AppButton>
              <AppButton variant="danger" @click="handleDelete(t.id)">删除</AppButton>
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          title="暂无导师记录"
          description="点击右上角「新增导师」或「批量导入」开始添加"
        />
      </AppCard>
    </section>

    <!-- 新增/编辑弹窗 -->
    <Teleport to="body">
      <div v-if="modalVisible" class="dialog-overlay" @click="closeModal">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">{{ isEditMode ? '编辑导师' : '新增导师' }}</h2>
            <el-icon class="close-btn" @click="closeModal"><Close /></el-icon>
          </div>
          <form class="dialog-body" @submit.prevent="handleSubmit">
            <div class="form-grid">
              <div class="form-field">
                <label class="form-label">登录用户名 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.username"
                  placeholder="请输入登录用户名"
                  @blur="onFieldBlur('username')"
                  @input="clearFieldError('username')"
                />
                <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">工号 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.teacherNumber"
                  placeholder="请输入工号"
                  @blur="onFieldBlur('teacherNumber')"
                  @input="clearFieldError('teacherNumber')"
                />
                <span v-if="errors.teacherNumber" class="field-error">{{ errors.teacherNumber }}</span>
              </div>
              <!-- v2 创建导师时 password 必填；编辑时不显示 -->
              <div v-if="!isEditMode" class="form-field">
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
                <label class="form-label">院系 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.department"
                  placeholder="请输入院系"
                  @blur="onFieldBlur('department')"
                  @input="clearFieldError('department')"
                />
                <span v-if="errors.department" class="field-error">{{ errors.department }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">职称</label>
                <el-input v-model="form.title" placeholder="请输入职称" />
              </div>
              <div class="form-field">
                <label class="form-label">招生名额</label>
                <el-input
                  v-model.number="form.maxQuota"
                  type="number"
                  min="0"
                  @blur="onFieldBlur('maxQuota')"
                  @input="clearFieldError('maxQuota')"
                />
                <span v-if="errors.maxQuota" class="field-error">{{ errors.maxQuota }}</span>
              </div>
              <div class="form-field">
                <label class="form-label">研究方向</label>
                <el-input v-model="form.researchArea" placeholder="请输入研究方向" />
              </div>
              <div class="form-field form-field-full">
                <label class="form-label">个人简介</label>
                <el-input
                  v-model="form.profile"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入个人简介"
                />
              </div>
              <div class="form-field form-field-full">
                <label class="form-label">指导课题</label>
                <el-input v-model="form.projectDirection" placeholder="请输入指导课题" />
              </div>
              <div class="form-field form-field-full">
                <label class="form-label">研究课题</label>
                <el-input
                  v-model="form.researchTopics"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入研究课题，多个用换行分隔"
                />
              </div>
              <div class="form-field form-field-full">
                <label class="form-label">招生要求</label>
                <el-input
                  v-model="form.requirements"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入招生要求"
                />
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

    <!-- 设置名额弹窗 -->
    <Teleport to="body">
      <div v-if="quotaModalVisible" class="dialog-overlay" @click="closeQuotaModal">
        <div class="dialog-content dialog-content-sm" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">设置招生名额</h2>
            <el-icon class="close-btn" @click="closeQuotaModal"><Close /></el-icon>
          </div>
          <form class="dialog-body" @submit.prevent="submitQuota">
            <div class="quota-info-row">
              <span class="quota-info-label">导师</span>
              <span class="quota-info-value">{{ quotaTeacherName }}</span>
            </div>
            <div class="quota-info-row">
              <span class="quota-info-label">已录取</span>
              <span class="quota-info-value">{{ quotaCurrentAdmitted }} 人</span>
            </div>
            <div class="form-field">
              <label class="form-label">招生名额上限</label>
              <el-input v-model.number="quotaInput" type="number" min="0" />
              <p v-if="quotaError" class="form-error">{{ quotaError }}</p>
              <p class="form-hint">名额不能少于已录取人数</p>
            </div>
            <div class="quota-preview">
              <QuotaBadge :admitted="quotaCurrentAdmitted" :max="quotaInput" />
            </div>
            <div class="dialog-footer">
              <AppButton type="button" variant="tertiary" @click="closeQuotaModal">取消</AppButton>
              <AppButton type="submit" variant="primary">确定</AppButton>
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
.teacher-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  /* 用 minmax(0, Xfr) 禁止列被内容撑开，确保表头与行列宽严格一致。
     之前用 1fr（=minmax(auto,1fr)），表头与行是独立 grid 容器，
     内容 min-content 不同导致列宽计算不一致，表头 col-action=149px 而行 col-action=263px。
     操作列 3.5fr 确保按钮有足够空间，flex-wrap 允许必要时换行。 */
  grid-template-columns: minmax(0,1fr) minmax(0,1fr) minmax(0,1.2fr) minmax(0,0.9fr) minmax(0,1.3fr) minmax(0,0.8fr) minmax(0,0.8fr) minmax(0,0.9fr) minmax(0,3.5fr);
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

.col-id {
  font-family: var(--font-mono);
  font-size: var(--text-mono);
  color: var(--color-ink-muted);
}

.col-name {
  font-weight: 500;
  color: var(--color-ink);
}

.col-area {
  color: var(--color-ink-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-quota,
.col-admitted {
  font-variant-numeric: tabular-nums;
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
  width: 560px;
  max-width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

.dialog-content-sm {
  width: 440px;
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

.form-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-semantic-error);
}

/* 名额信息 */
.quota-info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--color-hairline);
}

.quota-info-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.quota-info-value {
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-ink);
}

.quota-preview {
  display: flex;
  justify-content: center;
  padding: var(--spacing-sm) 0;
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
