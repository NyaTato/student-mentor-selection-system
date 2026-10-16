<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Bell,
  Calendar,
  DataAnalysis,
  Document,
  Link,
  List,
  Monitor,
  Reading,
  Refresh,
  Setting,
  Tickets,
  Timer,
  UserFilled,
  Operation,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import BaseLayout from './BaseLayout.vue'
import NavItem from '@/components/base/NavItem.vue'
import NavBrand from '@/components/base/NavBrand.vue'
import NavGroupLabel from '@/components/base/NavGroupLabel.vue'
import NavDivider from '@/components/base/NavDivider.vue'
import NavLogout from '@/components/base/NavLogout.vue'
import AcademicYearSelector from '@/components/base/AcademicYearSelector.vue'

const route = useRoute()
const authStore = useAuthStore()

/* Stripe 主题切换 — 进入 Dashboard 时切换为浅色 Stripe 体系 */
const isStripePage = computed(() => route.path === '/admin/dashboard')
</script>

<template>
  <div :class="{ 'stripe-theme': isStripePage }">
    <BaseLayout>
      <template #header>
        <AcademicYearSelector variant="selector" />
      </template>
      <template #sidebar>
        <NavBrand
          :name="authStore.user?.name ?? '管理员'"
          subtitle="管理员"
          :icon="UserFilled"
        />
        <NavItem to="/admin/dashboard" label="统计分析" :icon="DataAnalysis" />
        <NavGroupLabel label="用户管理" />
        <NavItem to="/admin/students" label="学生管理" :icon="Reading" />
        <NavItem to="/admin/teachers" label="导师管理" :icon="UserFilled" />
        <NavItem to="/admin/administrators" label="管理员管理" :icon="Setting" />

        <NavGroupLabel label="系统管理" />
        <NavItem to="/admin/system-state" label="状态控制" :icon="Refresh" />
        <NavItem to="/admin/schedule" label="时间切换" :icon="Timer" />
        <NavItem to="/admin/announcements" label="公告管理" :icon="Bell" />
        <NavItem to="/admin/manual-assignment" label="人工分配" :icon="Link" />
        <NavItem to="/admin/auto-assignment" label="自动分配" :icon="Operation" />
        <NavItem to="/admin/assignment-results" label="分配结果" :icon="List" />
        <NavItem to="/admin/logs" label="系统日志" :icon="Tickets" />
        <NavItem to="/admin/monitoring" label="系统监控" :icon="Monitor" />

        <NavGroupLabel label="数据管理" />
        <NavItem to="/admin/academic-year" label="学年管理" :icon="Calendar" />
        <NavItem to="/admin/excel-import" label="Excel 导入" :icon="Document" />
        <NavItem to="/admin/import-result" label="导入结果" :icon="Document" />

        <NavDivider />
        <NavLogout />
      </template>

      <RouterView />
    </BaseLayout>
  </div>
</template>
