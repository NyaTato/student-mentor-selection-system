import { defineStore } from 'pinia'
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { SystemState } from '@/types'
import { useSharedStore } from './shared'

/**
 * System State Store — 顶层 Header 显示用
 *
 * 委托 sharedStore.systemState（数据只存在于当前标签页内存，不做跨标签页广播）。
 * BaseLayout.vue 通过此 store 显示当前系统状态。
 */
export const useSystemStateStore = defineStore('systemState', () => {
  const sharedStore = useSharedStore()
  const { systemState } = storeToRefs(sharedStore)

  const stateLabel: Record<SystemState, string> = {
    [SystemState.INIT]: '未开启',
    [SystemState.FIRST_ROUND_OPEN]: '第一轮填报中',
    [SystemState.TEACHER_REVIEW]: '导师筛选阶段',
    [SystemState.SECOND_ROUND_OPEN]: '第二轮报名中',
    [SystemState.AUTO_ASSIGN]: '自动分配中',
    [SystemState.FINISHED]: '结束',
  }

  const currentState = computed(() => systemState.value)
  const label = computed(() => stateLabel[systemState.value])

  return {
    currentState,
    label,
  }
})
