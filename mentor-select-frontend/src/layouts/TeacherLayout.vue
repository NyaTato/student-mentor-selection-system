<script setup lang="ts">
import {
  CircleCheck,
  DataAnalysis,
  HomeFilled,
  List,
  Reading,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import { useTeacherStore } from '@/stores/teacher'
import BaseLayout from './BaseLayout.vue'
import NavItem from '@/components/base/NavItem.vue'
import NavBrand from '@/components/base/NavBrand.vue'
import NavDivider from '@/components/base/NavDivider.vue'
import NavLogout from '@/components/base/NavLogout.vue'
import AcademicYearSelector from '@/components/base/AcademicYearSelector.vue'

const teacherStore = useTeacherStore()
</script>

<template>
  <BaseLayout>
    <template #header>
      <AcademicYearSelector variant="display" />
    </template>
    <template #sidebar>
      <NavBrand
        :name="teacherStore.currentTeacher?.name ?? ''"
        :subtitle="teacherStore.currentTeacher?.title ?? ''"
        :icon="UserFilled"
      />

      <NavItem to="/teacher/dashboard" label="首页" :icon="HomeFilled" />
      <NavItem to="/teacher/applications" label="申请列表" :icon="List" />
      <NavItem to="/teacher/admission" label="录取管理" :icon="CircleCheck" />
      <NavItem to="/teacher/assigned-students" label="已指导学生" :icon="Reading" />
      <NavItem to="/teacher/quota" label="名额概览" :icon="DataAnalysis" />
      <NavItem to="/teacher/personal-info" label="个人信息" :icon="User" />

      <NavDivider />
      <NavLogout />
    </template>

    <RouterView />
  </BaseLayout>
</template>
