<script setup lang="ts">
import { computed } from 'vue'
import { Calendar } from '@element-plus/icons-vue'
import { useAdminStore } from '@/stores/admin'
import { AcademicYearStatus } from '@/types'

/* DISPLAY 变体：学生/导师端仅显示文本，不可点击 */
withDefaults(
  defineProps<{
    variant?: 'selector' | 'display'
  }>(),
  {
    variant: 'selector',
  },
)

const adminStore = useAdminStore()

const currentYear = computed(() => adminStore.currentAcademicYear)
const years = computed(() =>
  [...adminStore.academicYears].sort((a, b) => b.startYear - a.startYear),
)

function statusLabel(status: AcademicYearStatus): string {
  switch (status) {
    case AcademicYearStatus.ACTIVE:
      return '进行中'
    case AcademicYearStatus.CLOSED:
      return '已结束'
    case AcademicYearStatus.DRAFT:
      return '草稿'
    default:
      return '—'
  }
}

async function handleSwitch(id: number) {
  await adminStore.switchAcademicYear(id)
}
</script>

<template>
  <!-- 管理员顶栏全局选择器 -->
  <el-select
    v-if="variant === 'selector'"
    :model-value="adminStore.currentAcademicYearId"
    class="year-selector"
    size="small"
    @change="handleSwitch"
  >
    <el-option
      v-for="y in years"
      :key="y.id"
      :value="y.id"
      :label="`${y.name} · ${statusLabel(y.status)}`"
    />
  </el-select>

  <!-- 学生/导师端只读文本 -->
  <span v-else class="year-display">
    <el-icon class="year-display-icon"><Calendar /></el-icon>
    <span class="year-display-text">{{ currentYear?.name ?? '—' }}</span>
  </span>
</template>

<style scoped>
.year-selector {
  width: 200px;
}

.year-display {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

.year-display-icon {
  font-size: 14px;
  color: var(--color-ink-subtle);
}

.year-display-text {
  font-weight: 500;
}
</style>
