<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAdminStore } from '@/stores/admin'
import { UserRole } from '@/types'
import AppButton from '@/components/base/AppButton.vue'
import AppCard from '@/components/base/AppCard.vue'
import ExcelUpload from '@/components/base/ExcelUpload.vue'
import ImportTaskList from '@/components/base/ImportTaskList.vue'

const adminStore = useAdminStore()
const route = useRoute()
const router = useRouter()

/* 角色选择 — 默认学生 */
type ImportRole = UserRole.STUDENT | UserRole.TEACHER | UserRole.ADMIN
const selectedRole = ref<ImportRole>(
  (route.query.role as ImportRole) || UserRole.STUDENT,
)

function roleLabel(role: ImportRole): string {
  switch (role) {
    case UserRole.STUDENT:
      return '学生'
    case UserRole.TEACHER:
      return '导师'
    case UserRole.ADMIN:
      return '管理员'
    default:
      return '—'
  }
}

/* 模板字段提示 */
const templateFields = computed(() => {
  switch (selectedRole.value) {
    case UserRole.STUDENT:
      return ['username', 'name', 'studentId', 'major', 'grade', 'department', 'phone']
    case UserRole.TEACHER:
      return ['username', 'name', 'department', 'title', 'researchArea', 'maxQuota']
    case UserRole.ADMIN:
      return ['username', 'name']
    default:
      return []
  }
})

/* 当前选择的文件 */
const selectedFile = ref<File | null>(null)
const isImporting = ref(false)

function handleFileSelect(file: File) {
  selectedFile.value = file
}

/* Mock：解析 Excel 为行数据（实际由后端解析，前端仅 Mock） */
function mockParseExcel(file: File): Array<Record<string, string>> {
  /* 根据文件名大小生成 Mock 行数据 */
  const rows: Array<Record<string, string>> = []
  const baseCount = Math.max(1, Math.floor(file.size / 100))
  for (let i = 0; i < baseCount; i++) {
    const row: Record<string, string> = {}
    templateFields.value.forEach((field, idx) => {
      switch (field) {
        case 'username':
          row[field] = `${selectedRole.value.toLowerCase()}_${Date.now().toString().slice(-4)}_${i}`
          break
        case 'name':
          row[field] = `测试${roleLabel(selectedRole.value)}${i + 1}`
          break
        case 'studentId':
          row[field] = `2026${String(i + 1).padStart(4, '0')}`
          break
        case 'maxQuota':
          row[field] = String(5 + (i % 5))
          break
        default:
          row[field] = `${field}-${idx}`
      }
    })
    rows.push(row)
  }
  return rows
}

async function handleImport() {
  if (!selectedFile.value) {
    alert('请先选择 Excel 文件')
    return
  }
  isImporting.value = true
  try {
    /* Mock 解析 */
    const rows = mockParseExcel(selectedFile.value)
    const taskId = adminStore.createImportTask(
      selectedRole.value,
      selectedFile.value.name,
      selectedFile.value.size,
      rows,
    )
    alert(`导入任务已创建（任务 ID：${taskId}），共处理 ${rows.length} 行`)
    selectedFile.value = null
    /* 跳转到结果页 */
    router.push(`/admin/import-result?taskId=${taskId}`)
  } finally {
    isImporting.value = false
  }
}

/* 下载 Mock 模板 */
function downloadTemplate() {
  const fields = templateFields.value
  const csv = fields.join(',') + '\n'
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${roleLabel(selectedRole.value)}-import-template.csv`
  link.click()
  URL.revokeObjectURL(url)
}

/* 历史任务（按角色过滤） */
const filteredTasks = computed(() => {
  if (route.query.role) {
    return adminStore.importTasks.filter((t) => t.role === selectedRole.value)
  }
  return adminStore.importTasks
})

const roleOptions: { label: string; value: ImportRole }[] = [
  { label: '学生', value: UserRole.STUDENT },
  { label: '导师', value: UserRole.TEACHER },
  { label: '管理员', value: UserRole.ADMIN },
]
</script>

<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">Excel 批量导入</h1>
      <p class="page-description">通过 Excel 文件批量导入学生、导师或管理员账号</p>
    </div>

    <!-- 角色选择 -->
    <section class="section">
      <h2 class="section-title">选择导入角色</h2>
      <AppCard variant="default">
        <el-radio-group v-model="selectedRole">
          <el-radio-button
            v-for="opt in roleOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
      </AppCard>
    </section>

    <!-- 上传区 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">上传 Excel 文件</h2>
        <AppButton variant="tertiary" @click="downloadTemplate">
          下载模板
        </AppButton>
      </div>
      <AppCard variant="default">
        <ExcelUpload @select="handleFileSelect" />

        <!-- 模板字段说明 -->
        <div class="template-info">
          <h4 class="template-title">{{ roleLabel(selectedRole) }}模板字段</h4>
          <div class="template-fields">
            <span v-for="f in templateFields" :key="f" class="field-chip">{{ f }}</span>
          </div>
          <p class="template-hint">
            字段以英文逗号分隔，第一行为表头。重复 username 将自动跳过。
          </p>
        </div>

        <!-- 导入按钮 -->
        <div class="import-actions">
          <AppButton
            variant="primary"
            :disabled="!selectedFile || isImporting"
            @click="handleImport"
          >
            {{ isImporting ? '导入中…' : '开始导入' }}
          </AppButton>
        </div>
      </AppCard>
    </section>

    <!-- 历史任务 -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">导入历史</h2>
        <span class="section-count">共 {{ filteredTasks.length }} 个任务</span>
      </div>
      <AppCard variant="default">
        <ImportTaskList :tasks="filteredTasks" />
      </AppCard>
    </section>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
}

.page-header {
  margin-bottom: var(--spacing-lg);
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
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

.section-count {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.template-info {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.template-title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.template-fields {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.field-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--spacing-sm);
  background: var(--color-surface-3);
  border-radius: var(--rounded-pill);
  font-size: var(--text-caption);
  color: var(--color-ink-muted);
  font-family: var(--font-mono, monospace);
}

.template-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.import-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--color-hairline);
}
</style>
