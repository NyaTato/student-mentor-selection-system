<script setup lang="ts">
import { ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
import AppCard from '@/components/base/AppCard.vue'
import AppButton from '@/components/base/AppButton.vue'
import StatusBadge from '@/components/base/StatusBadge.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import type { Announcement } from '@/types'
import { formatDateTime } from '@/composables/useFormatTime'

const adminStore = useAdminStore()

/* 新增/编辑弹窗状态 */
const modalVisible = ref(false)
const editingId = ref<number | null>(null)
/* 编辑时记录原始发布状态——store 的 updateAnnouncement 仅支持 title/content，
   published 变更需要单独调用 toggleAnnouncementPublish */
const originalPublished = ref(false)
const form = ref({ title: '', content: '', published: false })

/* 内容预览——超过阈值截断（R7-04：双选通知、时间安排等较长内容） */
function previewContent(content: string, max = 120): string {
  if (content.length <= max) return content
  return content.slice(0, max) + '…'
}

function openAddModal() {
  editingId.value = null
  originalPublished.value = false
  form.value = { title: '', content: '', published: false }
  modalVisible.value = true
}

function openEditModal(ann: Announcement) {
  editingId.value = ann.id
  originalPublished.value = ann.published
  form.value = {
    title: ann.title,
    content: ann.content,
    published: ann.published,
  }
  modalVisible.value = true
}

function closeModal() {
  modalVisible.value = false
}

async function handleSubmit() {
  const title = form.value.title.trim()
  const content = form.value.content.trim()
  if (!title) {
    alert('请输入公告标题')
    return
  }
  if (!content) {
    alert('请输入公告内容')
    return
  }
  if (editingId.value === null) {
    await adminStore.addAnnouncement({ title, content, published: form.value.published })
    alert('公告添加成功')
  } else {
    await adminStore.updateAnnouncement(editingId.value, { title, content })
    /* 编辑弹窗内若修改了发布状态，调用 toggle 同步 */
    if (form.value.published !== originalPublished.value) {
      await adminStore.toggleAnnouncementPublish(editingId.value)
    }
    alert('公告修改成功')
  }
  closeModal()
}

/* R7-02 / R7-03：发布/取消发布切换 */
async function handleTogglePublish(ann: Announcement) {
  await adminStore.toggleAnnouncementPublish(ann.id)
}

async function handleDelete(ann: Announcement) {
  if (!confirm(`确定删除公告「${ann.title}」吗？此操作不可撤销。`)) return
  await adminStore.deleteAnnouncement(ann.id)
}
</script>

<template>
  <div class="page-container">
    <h1 class="page-title">公告管理</h1>
    <p class="page-description">管理系统公告（双选通知、时间安排等）</p>

    <!-- 工具栏 -->
    <div class="toolbar">
      <p class="toolbar-hint">
        共 {{ adminStore.announcements.length }} 条公告，已发布
        {{ adminStore.announcements.filter((a) => a.published).length }} 条
      </p>
      <div class="toolbar-actions">
        <AppButton variant="primary" @click="openAddModal">发布公告</AppButton>
      </div>
    </div>

    <!-- 公告列表 -->
    <section class="section">
      <h2 class="section-title">公告列表</h2>
      <EmptyState
        v-if="adminStore.announcements.length === 0"
        title="暂无公告"
        description="点击「发布公告」创建第一条系统公告"
      />
      <div v-else class="announcement-list">
        <AppCard
          v-for="ann in adminStore.announcements"
          :key="ann.id"
          variant="default"
        >
          <div class="announcement-header">
            <h3 class="announcement-title">{{ ann.title }}</h3>
            <StatusBadge
              :variant="ann.published ? 'success' : 'default'"
              :label="ann.published ? '已发布' : '未发布'"
            />
          </div>

          <p class="announcement-content">{{ previewContent(ann.content) }}</p>

          <div class="announcement-meta">
            <span class="meta-item">
              <span class="meta-label">创建时间</span>
              <span class="meta-value">{{ formatDateTime(ann.createdAt) }}</span>
            </span>
            <span class="meta-item">
              <span class="meta-label">更新时间</span>
              <span class="meta-value">{{ formatDateTime(ann.updatedAt) }}</span>
            </span>
          </div>

          <div class="announcement-actions">
            <AppButton variant="tertiary" @click="openEditModal(ann)">编辑</AppButton>
            <AppButton
              :variant="ann.published ? 'secondary' : 'primary'"
              @click="handleTogglePublish(ann)"
            >
              {{ ann.published ? '取消发布' : '发布' }}
            </AppButton>
            <AppButton variant="danger" @click="handleDelete(ann)">删除</AppButton>
          </div>
        </AppCard>
      </div>
    </section>

    <!-- 新增/编辑弹窗 -->
    <div v-if="modalVisible" class="modal-overlay" @click.self="closeModal">
      <div class="modal-card">
        <h3 class="modal-title">
          {{ editingId === null ? '发布公告' : '编辑公告' }}
        </h3>

        <div class="form-group">
          <label class="form-label" for="ann-title">
            标题<span class="form-required">*</span>
          </label>
          <el-input
            id="ann-title"
            v-model="form.title"
            placeholder="请输入公告标题"
            maxlength="100"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="ann-content">
            内容<span class="form-required">*</span>
          </label>
          <el-input
            id="ann-content"
            v-model="form.content"
            type="textarea"
            :rows="6"
            placeholder="请输入公告内容（双选通知、时间安排等）"
          />
        </div>

        <div class="form-group form-group-row">
          <el-checkbox v-model="form.published">
            立即发布（发布后学生可见，未发布仅管理员可见）
          </el-checkbox>
        </div>

        <div class="modal-actions">
          <AppButton variant="secondary" @click="closeModal">取消</AppButton>
          <AppButton variant="primary" @click="handleSubmit">确定</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-container {
  max-width: 1000px;
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
  margin-bottom: var(--spacing-lg);
}

.toolbar-hint {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.toolbar-actions {
  display: flex;
  gap: var(--spacing-sm);
}

/* Section */
.section {
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.section-title {
  font-size: var(--text-subhead);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

/* 公告列表 */
.announcement-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.announcement-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.announcement-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
  line-height: var(--text-card-title-line);
  word-break: break-word;
}

.announcement-content {
  font-size: var(--text-body-sm);
  line-height: var(--text-body-sm-line);
  color: var(--color-ink-muted);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: var(--spacing-sm);
}

.announcement-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--color-hairline);
  margin-bottom: var(--spacing-sm);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.meta-label {
  font-size: var(--text-caption);
  color: var(--color-ink-subtle);
}

.meta-value {
  font-size: var(--text-caption);
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
}

.announcement-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  justify-content: flex-end;
}

/* 弹窗 — 遮罩层 + 白色卡片 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: var(--color-semantic-overlay);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--spacing-lg);
}

.modal-card {
  background: var(--color-surface-1);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--spacing-lg);
  width: 100%;
  max-width: 560px;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.modal-title {
  font-size: var(--text-card-title);
  font-weight: var(--text-card-title-weight);
  color: var(--color-ink);
}

/* 表单 */
.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group-row {
  flex-direction: row;
  align-items: center;
  gap: var(--spacing-sm);
}

.form-label {
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-ink);
}

.form-required {
  color: var(--color-semantic-error);
  margin-left: 2px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xs);
}

/* 响应式 */
@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-actions {
    justify-content: flex-end;
  }

  .announcement-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .announcement-actions {
    justify-content: flex-start;
  }
}
</style>
