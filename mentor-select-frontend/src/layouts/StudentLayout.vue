<script setup lang="ts">
import { computed } from 'vue'
import {
  DataAnalysis,
  Document,
  EditPen,
  HomeFilled,
  List,
  Reading,
  Tickets,
  User,
} from '@element-plus/icons-vue'
import { useStudentStore } from '@/stores/student'
import { SystemState } from '@/types'
import BaseLayout from './BaseLayout.vue'
import NavItem from '@/components/base/NavItem.vue'
import NavBrand from '@/components/base/NavBrand.vue'
import NavGroupLabel from '@/components/base/NavGroupLabel.vue'
import NavDivider from '@/components/base/NavDivider.vue'
import NavLogout from '@/components/base/NavLogout.vue'
import AcademicYearSelector from '@/components/base/AcademicYearSelector.vue'

const studentStore = useStudentStore()

const state = computed(() => studentStore.systemState)

/* 权限矩阵 — 对应 PROJECT.md 9.1 */
const showFirstRound = computed(() => state.value === SystemState.FIRST_ROUND_OPEN)
const showFirstRoundMy = computed(
  () => state.value === SystemState.FIRST_ROUND_OPEN || state.value === SystemState.TEACHER_REVIEW,
)
const showFirstRoundResult = computed(() => state.value === SystemState.TEACHER_REVIEW)
const showSecondRound = computed(
  () => state.value === SystemState.SECOND_ROUND_OPEN && studentStore.isRejectedInRound1,
)
const showFinalResult = computed(() => state.value === SystemState.FINISHED)
const showHistory = computed(() => state.value === SystemState.FINISHED)
</script>

<template>
  <BaseLayout>
    <template #header>
      <AcademicYearSelector variant="display" />
    </template>
    <template #sidebar>
      <NavBrand
        :name="studentStore.currentStudent?.name ?? ''"
        :subtitle="studentStore.currentStudent?.studentId ?? ''"
        :icon="User"
      />
      <NavItem to="/student/dashboard" label="首页" :icon="HomeFilled" />
      <NavItem to="/student/personal-info" label="个人信息" :icon="User" />

      <!-- 第一轮专属页面 -->
      <template v-if="showFirstRound">
        <NavGroupLabel label="第一轮" />
        <NavItem to="/student/teachers" label="导师列表" :icon="List" />
        <NavItem to="/student/first-round/apply" label="填报志愿" :icon="EditPen" />
      </template>

      <template v-if="showFirstRoundMy">
        <NavItem to="/student/first-round/my" label="我的志愿" :icon="Document" />
      </template>

      <template v-if="showFirstRoundResult">
        <NavItem to="/student/first-round/result" label="一轮结果" :icon="DataAnalysis" />
      </template>

      <!-- 第二轮专属页面（仅被拒学生可见） -->
      <template v-if="showSecondRound">
        <NavGroupLabel label="第二轮" />
        <NavItem to="/student/second-round/teachers" label="二轮导师列表" :icon="List" />
        <NavItem to="/student/second-round/my" label="我的二轮申请" :icon="Document" />
      </template>

      <!-- 结束后通用页面 -->
      <template v-if="showFinalResult">
        <NavItem to="/student/final-result" label="最终结果" :icon="Reading" />
      </template>

      <template v-if="showHistory">
        <NavItem to="/student/history" label="历史记录" :icon="Tickets" />
      </template>

      <NavDivider />
      <NavLogout />
    </template>

    <RouterView />
  </BaseLayout>
</template>
