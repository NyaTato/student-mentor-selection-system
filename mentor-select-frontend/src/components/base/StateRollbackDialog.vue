<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { WarningFilled, ArrowRight } from '@element-plus/icons-vue'
import AppButton from './AppButton.vue'
import AppDialog from './AppDialog.vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps<{
  visible: boolean
  fromLabel: string
  toLabel: string
}>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', reason: string): void
}>()

const reason = ref('')

/* R12-03：回退原因最少 10 字符 */
const reasonError = computed(() => {
  if (!reason.value.trim()) return '请填写回退原因'
  if (reason.value.trim().length < 10) return '回退原因至少需要 10 个字符'
  return ''
})

const canConfirm = computed(() => reasonError.value === '')

/* 弹窗打开时重置 */
watch(
  () => props.visible,
  (v) => {
    if (v) reason.value = ''
  },
)

function close() {
  emit('update:visible', false)
}

function handleConfirm() {
  if (!canConfirm.value) return
  emit('confirm', reason.value.trim())
  close()
}
</script>

<template>
  <AppDialog
    :visible="visible"
    variant="danger"
    @update:visible="emit('update:visible', $event)"
  >
    <template #header>
      <h2 class="dialog-title dialog-title--danger">
        <el-icon class="title-icon"><WarningFilled /></el-icon>
        确认回退系统状态
      </h2>
    </template>

    <!-- 状态流转 -->
    <div class="state-flow">
      <div class="state-block">
        <span class="state-block-label">当前状态</span>
        <StatusBadge variant="default" :label="fromLabel" />
      </div>
      <span class="state-arrow">
        <el-icon><ArrowRight /></el-icon>
      </span>
      <div class="state-block">
        <span class="state-block-label">目标状态</span>
        <StatusBadge variant="warning" :label="toLabel" />
      </div>
    </div>

    <!-- 回退原因 -->
    <div class="form-field">
      <label class="form-label">
        回退原因 <span class="required">*</span>
        <span class="form-hint">（至少 10 个字符）</span>
      </label>
      <el-input
        v-model="reason"
        type="textarea"
        :rows="4"
        placeholder="请说明回退原因，例如：发现第一轮填报数据异常，需要回退让学生重新填报"
        maxlength="200"
        show-word-limit
      />
      <p v-if="reason && reasonError" class="form-error">{{ reasonError }}</p>
    </div>

    <!-- 警告提示 -->
    <div class="warning-block">
      <el-icon class="warning-icon"><WarningFilled /></el-icon>
      <p class="warning-text">
        回退不删除业务数据，但学生/导师可修改已提交的内容。
      </p>
    </div>

    <template #footer>
      <AppButton variant="secondary" @click="close">取消</AppButton>
      <AppButton variant="danger" :disabled="!canConfirm" @click="handleConfirm">
        确认回退
      </AppButton>
    </template>
  </AppDialog>
</template>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  margin: 0;
}

.dialog-title--danger {
  color: var(--color-semantic-error);
}

.title-icon {
  font-size: 20px;
}

.state-flow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-surface-2);
  border-radius: var(--rounded-md);
}

.state-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.state-block-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.state-arrow {
  font-size: var(--text-headline);
  color: var(--color-ink-subtle);
  font-weight: 300;
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
  color: var(--color-ink-subtle);
  font-weight: 400;
  margin-left: var(--spacing-xs);
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-semantic-error);
}

.warning-block {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-warning-bg);
  border-radius: var(--rounded-md);
}

.warning-icon {
  font-size: 18px;
  color: var(--color-semantic-warning);
  flex-shrink: 0;
}

.warning-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}
</style>
