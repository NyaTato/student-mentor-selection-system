<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ExcelImportButton from '@/components/base/ExcelImportButton.vue'
import type { AdminInfo } from '@/types'
import { formatDateTime } from '@/composables/useFormatTime'

const adminStore = useAdminStore()
const router = useRouter()

/* ========== 搜索与筛选 ========== */
const searchKeyword = ref('')

const filteredAdmins = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return adminStore.admins
  return adminStore.admins.filter(
    (a) =>
      a.name.toLowerCase().includes(kw) ||
      a.username.toLowerCase().includes(kw),
  )
})

/* ========== 新增/编辑弹窗 ========== */
const modalVisible = ref(false)
const isEditMode = ref(false)
const editingId = ref<number | null>(null)
/* v2 创建管理员时 password 必填；编辑时不修改密码 */
const form = ref({ username: '', name: '', password: '' })

function emptyForm() {
  return { username: '', name: '', password: '' }
}

/* ========== 表单实时验证（blur 时触发，与后端 Serializer 规则一致） ========== */
const errors = reactive<Record<string, string>>({
  username: '',
  name: '',
  password: '',
})

function validateField(field: keyof typeof errors): string {
  switch (field) {
    case 'username': {
      const v = form.value.username.trim()
      if (!v) return '请输入登录用户名'
      if (!/^[a-zA-Z0-9_]{3,20}$/.test(v)) return '用户名只能包含字母、数字、下划线，长度3-20位'
      return ''
    }
    case 'name': {
      const v = form.value.name.trim()
      if (!v) return '请输入姓名'
      return ''
    }
    case 'password': {
      if (isEditMode.value) return ''
      const v = form.value.password.trim()
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
  form.value = emptyForm()
  clearAllErrors()
  modalVisible.value = true
}

function openEditModal(admin: AdminInfo) {
  isEditMode.value = true
  editingId.value = admin.id
  /* 编辑模式下不修改密码，重置为空 */
  form.value = { username: admin.username, name: admin.name, password: '' }
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
  const username = form.value.username.trim()
  const name = form.value.name.trim()
  if (isEditMode.value && editingId.value !== null) {
    await adminStore.updateAdmin(editingId.value, { username, name })
    alert('修改管理员成功')
  } else {
    const result = await adminStore.addAdmin({
      username,
      name,
      password: form.value.password.trim(),
      createdAt: new Date().toISOString(),
    })
    if (result.success && result.generatedPassword) {
      ElMessageBox.alert(
        `初始密码：${result.generatedPassword}`,
        '管理员创建成功',
        { confirmButtonText: '已知晓' },
      )
    } else if (result.success) {
      alert('新增管理员成功')
    }
  }
  modalVisible.value = false
}

/* R5-01：账号不提供注册，仅由管理员管理。至少保留一个管理员（store 层强制） */
async function handleDelete(admin: AdminInfo) {
  try {
    await ElMessageBox.confirm(
      `确定删除管理员「${admin.name}」吗？此操作不可撤销。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  const ok = await adminStore.deleteAdmin(admin.id)
  if (!ok) {
    alert('删除失败：系统至少需要保留一个管理员账号')
    return
  }
  alert('删除成功')
}

/* ========== Excel 导入入口 ========== */
function goToExcelImport() {
  router.push('/admin/excel-import?role=ADMIN')
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">管理员管理</h1>
    <p class="page-description">管理员账号管理</p>

    <!-- 工具栏 — 与 StudentManagementView 完全一致，院系位置保留空白占位 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchKeyword"
          class="search-input"
          placeholder="按用户名或姓名搜索"
          clearable
        />
        <!-- 管理员无院系字段，保留占位以维持视觉统一 -->
        <div class="dept-placeholder" aria-hidden="true"></div>
      </div>
      <div class="toolbar-right">
        <AppButton variant="primary" @click="openAddModal">新增管理员</AppButton>
        <ExcelImportButton label="Excel 导入" @click="goToExcelImport" />
      </div>
    </div>

    <!-- 管理员表格 -->
    <section class="section">
      <AppCard variant="default">
        <div v-if="filteredAdmins.length" class="admin-table">
          <div class="table-header">
            <div class="col-username">用户名</div>
            <div class="col-name">姓名</div>
            <div class="col-time">创建时间</div>
            <div class="col-time">最近登录</div>
            <div class="col-action">操作</div>
          </div>
          <div v-for="admin in filteredAdmins" :key="admin.id" class="table-row">
            <div class="col-username">{{ admin.username }}</div>
            <div class="col-name">{{ admin.name }}</div>
            <div class="col-time">{{ formatDateTime(admin.createdAt) }}</div>
            <div class="col-time">{{ formatDateTime(admin.lastLoginAt) }}</div>
            <div class="col-action">
              <AppButton variant="tertiary" @click="openEditModal(admin)">编辑</AppButton>
              <AppButton variant="danger" @click="handleDelete(admin)">删除</AppButton>
            </div>
          </div>
        </div>
        <EmptyState
          v-else
          :title="adminStore.admins.length === 0 ? '暂无管理员记录' : '未找到匹配结果'"
          :description="
            adminStore.admins.length === 0
              ? '点击右上角「新增管理员」或「批量导入」开始添加'
              : '尝试修改搜索关键字'
          "
        />
      </AppCard>
    </section>

    <!-- 新增/编辑弹窗 — 与 StudentManagementView 完全一致 -->
    <Teleport to="body">
      <div v-if="modalVisible" class="dialog-overlay" @click="closeModal">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">{{ isEditMode ? '编辑管理员' : '新增管理员' }}</h2>
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
                <label class="form-label">姓名 <span style="color: var(--color-semantic-error)">*</span></label>
                <el-input
                  v-model="form.name"
                  placeholder="请输入姓名"
                  @blur="onFieldBlur('name')"
                  @input="clearFieldError('name')"
                />
                <span v-if="errors.name" class="field-error">{{ errors.name }}</span>
              </div>
              <!-- v2 创建管理员时 password 必填；编辑时不显示 -->
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

/* 工具栏 — 与 StudentManagementView 完全一致 */
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

/* 院系位置占位 — 模拟 Student 的 el-select flex 行为（width:100% + flex-shrink:1）。
   el-select 的 flex-basis 100% 会抢占空间，把 searchInput 压到 min-width 200px。
   dept-placeholder 用 flex: 0 1 100% 复现此行为，确保 searchInput 宽度与 Student 一致（200px）。
   实测：修复前 searchInput=241px（比 Student 宽 41px），修复后 searchInput=200px（与 Student 一致）。 */
.dept-placeholder {
  flex: 0 1 100%;
}

/* Section */
.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* 表格 — CSS Grid */
.admin-table {
  display: flex;
  flex-direction: column;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr 1.5fr 1.6fr;
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

.col-username {
  font-family: var(--font-mono);
  font-size: var(--text-mono);
  color: var(--color-ink-muted);
}

.col-name {
  font-weight: 500;
  color: var(--color-ink);
}

.col-time {
  color: var(--color-ink-muted);
  font-size: var(--text-caption);
}

.col-action {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

/* 弹窗 — 与 StudentManagementView 完全一致 */
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-top: var(--spacing-md);
}

/* 响应式 — 与 StudentManagementView 完全一致 */
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
