<script setup lang="ts">
import { Document } from '@element-plus/icons-vue'
import AppButton from './AppButton.vue'

defineProps<{
  label?: string
}>()
</script>

<template>
  <AppButton variant="secondary">
    <el-icon><Document /></el-icon>
    <span>{{ label ?? 'Excel 导入' }}</span>
  </AppButton>
</template>
