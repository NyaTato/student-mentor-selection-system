<script setup lang="ts">
import { ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import { AcademicYearStatus } from '@/types'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import AcademicYearCard from '@/components/base/AcademicYearCard.vue'
import EmptyState from '@/components/base/EmptyState.vue'

const adminStore = useAdminStore()

/* 新增学年弹窗 */
const createModalVisible = ref(false)
const newYearName = ref('')
const errorMessage = ref('')

function openCreateModal() {
  newYearName.value = ''
  errorMessage.value = ''
  createModalVisible.value = true
}

function closeCreateModal() {
  createModalVisible.value = false
  newYearName.value = ''
  errorMessage.value = ''
}

/* R9-01：学年格式 YYYY-YYYY，结束年份 = 开始年份 + 1 */
function validateName(name: string): string {
  const match = /^(\d{4})-(\d{4})$/.exec(name)
  if (!match) return '格式必须为 YYYY-YYYY，如 2026-2027'
  const startYear = Number(match[1])
  const endYear = Number(match[2])
  if (endYear !== startYear + 1) return '结束年份必须等于开始年份 + 1'
  if (adminStore.academicYears.some((y) => y.name === name)) return '该学年已存在'
  return ''
}

async function handleCreate() {
  const name = newYearName.value.trim()
  const err = validateName(name)
  if (err) {
    errorMessage.value = err
    return
  }
  const ok = await adminStore.createAcademicYear(name)
  if (!ok) {
    errorMessage.value = '创建失败，请检查格式或是否已存在'
    return
  }
  alert(`学年「${name}」创建成功`)
  closeCreateModal()
}

async function handleActivate(id: number) {
  const year = adminStore.academicYears.find((y) => y.id === id)
  if (!year) return
  if (
    !confirm(
      `确认激活学年「${year.name}」？\n激活后当前 ACTIVE 学年将被关闭，系统状态将重置为 INIT。`,
    )
  )
    return
  const ok = await adminStore.activateAcademicYear(id)
  if (!ok) {
    alert('激活失败：当前存在未结束的 ACTIVE 学年，或系统状态非 FINISHED')
    return
  }
  alert(`学年「${year.name}」已激活`)
}

async function handleClose(id: number) {
  const year = adminStore.academicYears.find((y) => y.id === id)
  if (!year) return
  if (!confirm(`确认关闭学年「${year.name}」？关闭后该学年变为只读。`)) return
  const ok = await adminStore.closeAcademicYear(id)
  if (!ok) {
    alert('关闭失败：系统状态必须为 FINISHED')
    return
  }
  alert(`学年「${year.name}」已关闭`)
}

const sortedYears = () =>
  [...adminStore.academicYears].sort((a, b) => {
    /* ACTIVE 优先，其次按开始年份降序 */
    const statusOrder: Record<AcademicYearStatus, number> = {
      [AcademicYearStatus.ACTIVE]: 0,
      [AcademicYearStatus.DRAFT]: 1,
      [AcademicYearStatus.CLOSED]: 2,
    }
    if (statusOrder[a.status] !== statusOrder[b.status]) {
      return statusOrder[a.status] - statusOrder[b.status]
    }
    return b.startYear - a.startYear
  })
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">学年管理</h1>
        <p class="page-description">管理学年创建、激活、关闭与切换</p>
      </div>
      <AppButton variant="primary" @click="openCreateModal">
        <el-icon><Plus /></el-icon>
        新增学年
      </AppButton>
    </div>

    <!-- 学年卡片网格 -->
    <section v-if="sortedYears().length" class="year-grid">
      <AcademicYearCard
        v-for="y in sortedYears()"
        :key="y.id"
        :year="y"
        @activate="handleActivate"
        @close="handleClose"
      />
    </section>
    <AppCard v-else variant="default">
      <EmptyState title="暂无学年" description="点击右上角「新增学年」开始创建" />
    </AppCard>

    <!-- 新增学年弹窗 -->
    <Teleport to="body">
      <div v-if="createModalVisible" class="dialog-overlay" @click="closeCreateModal">
        <div class="dialog-content" @click.stop>
          <div class="dialog-header">
            <h2 class="dialog-title">新增学年</h2>
            <button class="close-btn" type="button" @click="closeCreateModal">×</button>
          </div>
          <div class="dialog-body">
            <div class="form-field">
              <label class="form-label">学年名称 <span class="required">*</span></label>
              <el-input
                v-model="newYearName"
                placeholder="格式：2026-2027"
                maxlength="9"
              />
              <p class="form-hint">格式 YYYY-YYYY，结束年份 = 开始年份 + 1</p>
              <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
            </div>
          </div>
          <div class="dialog-footer">
            <AppButton variant="secondary" @click="closeCreateModal">取消</AppButton>
            <AppButton variant="primary" @click="handleCreate">创建</AppButton>
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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  flex-wrap: wrap;
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
}

.year-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: var(--spacing-md);
}

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
  width: 480px;
  max-width: 100%;
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
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: var(--color-ink-subtle);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--rounded-sm);
}

.close-btn:hover {
  background: var(--color-surface-3);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.required {
  color: var(--color-semantic-error);
}

.form-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-semantic-error);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  margin-top: var(--spacing-md);
}
</style>
