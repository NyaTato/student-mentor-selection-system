<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled, Delete, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'

const emit = defineEmits<{
  (e: 'select', file: File): void
}>()

const selectedFile = ref<File | null>(null)
const errorMessage = ref('')

const MAX_SIZE = 5 * 1024 * 1024 /* 5MB — R11-03 */
const ACCEPTED = ['.xlsx', '.xls']

function validate(file: File): string {
  const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase()
  if (!ACCEPTED.includes(ext)) {
    return '仅支持 .xlsx 和 .xls 格式文件'
  }
  if (file.size > MAX_SIZE) {
    return '文件大小不能超过 5MB'
  }
  return ''
}

function handleFile(file: File) {
  const err = validate(file)
  if (err) {
    errorMessage.value = err
    selectedFile.value = null
    ElMessage.warning(err)
    return
  }
  errorMessage.value = ''
  selectedFile.value = file
  emit('select', file)
}

/* el-upload 的 http-request 自定义处理，阻止自动上传 */
function customHttpRequest(options: { file: File }): void {
  handleFile(options.file)
}

/* el-upload before-upload 校验 */
function beforeUpload(file: File): boolean {
  const err = validate(file)
  if (err) {
    errorMessage.value = err
    ElMessage.warning(err)
    return false
  }
  return true
}

/* 兼容 el-upload 的 on-change 事件 */
function onFileChange(uploadFile: UploadFile): void {
  if (uploadFile.raw) {
    handleFile(uploadFile.raw)
  }
}

function removeFile(): void {
  selectedFile.value = null
  errorMessage.value = ''
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}
</script>

<template>
  <div class="excel-upload">
    <!-- 拖拽区 — 使用 el-upload drag 模式 -->
    <el-upload
      v-if="!selectedFile"
      drag
      :auto-upload="false"
      :show-file-list="false"
      accept=".xlsx,.xls"
      :before-upload="beforeUpload"
      :http-request="customHttpRequest"
      :on-change="onFileChange"
      class="upload-dragger"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <p class="upload-text">点击或拖拽 Excel 文件到此处</p>
      <p class="upload-hint">支持 .xlsx / .xls 格式，最大 5MB</p>
    </el-upload>

    <!-- 已选文件展示 -->
    <div v-else class="file-info">
      <el-icon class="file-icon"><Document /></el-icon>
      <div class="file-meta">
        <div class="file-name">{{ selectedFile.name }}</div>
        <div class="file-size">{{ formatSize(selectedFile.size) }}</div>
      </div>
      <el-button
        type="danger"
        text
        :icon="Delete"
        @click="removeFile"
      >
        移除
      </el-button>
    </div>

    <!-- 错误提示 -->
    <p v-if="errorMessage" class="upload-error">{{ errorMessage }}</p>
  </div>
</template>

<style scoped>
.excel-upload {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.upload-dragger {
  width: 100%;
}

.upload-dragger :deep(.el-upload-dragger) {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 160px;
  border: 2px dashed var(--color-hairline-strong);
  border-radius: var(--rounded-md);
  background: var(--color-surface-2);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  padding: var(--spacing-md);
}

.upload-dragger :deep(.el-upload-dragger:hover) {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.upload-dragger :deep(.el-upload-dragger.over) {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}

.upload-icon {
  font-size: 32px;
  color: var(--color-ink-subtle);
  margin-bottom: var(--spacing-sm);
}

.upload-text {
  font-size: var(--text-body);
  color: var(--color-ink);
  margin-bottom: var(--spacing-xs);
}

.upload-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-tertiary);
}

.file-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-surface-2);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
}

.file-icon {
  font-size: 24px;
  color: var(--color-primary);
}

.file-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.file-name {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
  font-weight: 500;
}

.file-size {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.upload-error {
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
  border-radius: var(--rounded-sm);
  font-size: var(--text-body-sm);
}
</style>
