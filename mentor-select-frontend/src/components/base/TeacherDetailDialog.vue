<script setup lang="ts">
import type { TeacherInfo } from '@/types'
import AppButton from './AppButton.vue'
import AppDialog from './AppDialog.vue'
import StatusBadge from './StatusBadge.vue'

defineProps<{
  teacher: TeacherInfo
  showApplyButton?: boolean
  applyButtonText?: string
  applyDisabled?: boolean
}>()

const emit = defineEmits<{
  close: []
  apply: [teacherId: number]
}>()
</script>

<template>
  <AppDialog
    :visible="true"
    :width="640"
    @update:visible="emit('close')"
  >
    <template #header>
      <div class="header-left">
        <h2 class="teacher-name">{{ teacher.name }}</h2>
        <StatusBadge :label="teacher.title" variant="default" />
      </div>
    </template>

    <!-- Basic Info -->
    <div class="dialog-section">
      <div class="section-label">基本信息</div>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-key">学院</span>
          <span class="info-val">{{ teacher.department }}</span>
        </div>
        <div class="info-item">
          <span class="info-key">研究方向</span>
          <span class="info-val">{{ teacher.researchArea }}</span>
        </div>
        <div class="info-item">
          <span class="info-key">招生名额</span>
          <span class="info-val">{{ teacher.maxQuota }} 人</span>
        </div>
        <div class="info-item">
          <span class="info-key">已录取</span>
          <span class="info-val">{{ teacher.currentAdmitted }} 人</span>
        </div>
      </div>
    </div>

    <!-- Profile -->
    <div class="dialog-section">
      <div class="section-label">个人简介</div>
      <p class="section-text">{{ teacher.profile }}</p>
    </div>

    <!-- Project Direction -->
    <div class="dialog-section">
      <div class="section-label">指导方向</div>
      <p class="section-text">{{ teacher.projectDirection }}</p>
    </div>

    <!-- Research Topics -->
    <div class="dialog-section">
      <div class="section-label">课题题目</div>
      <p class="section-text pre-wrap">{{ teacher.researchTopics }}</p>
    </div>

    <!-- Requirements -->
    <div class="dialog-section">
      <div class="section-label">对学生要求</div>
      <p class="section-text">{{ teacher.requirements }}</p>
    </div>

    <template v-if="showApplyButton" #footer>
      <AppButton variant="tertiary" @click="emit('close')">关闭</AppButton>
      <AppButton
        variant="primary"
        :disabled="applyDisabled"
        @click="emit('apply', teacher.id)"
      >
        {{ applyButtonText || '选择导师' }}
      </AppButton>
    </template>
  </AppDialog>
</template>

<style scoped>
.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.teacher-name {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
  margin: 0;
}

.dialog-section {
  margin-bottom: var(--spacing-md);
}

.section-label {
  font-size: var(--text-eyebrow);
  font-weight: var(--text-eyebrow-weight);
  letter-spacing: var(--text-eyebrow-spacing);
  color: var(--color-ink-tertiary);
  text-transform: uppercase;
  margin-bottom: var(--spacing-xs);
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-sm);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-key {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.info-val {
  font-size: var(--text-body-sm);
  color: var(--color-ink);
}

.section-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
  line-height: var(--text-body-sm-line);
}

.pre-wrap {
  white-space: pre-wrap;
}
</style>
