<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSharedStore } from '@/stores/shared'

const authStore = useAuthStore()
const sharedStore = useSharedStore()

/* 应用启动：恢复会话，若已登录则按当前角色从后端加载数据 */
onMounted(async () => {
  authStore.restore()
  if (authStore.isAuthenticated) {
    try {
      /* 显式传入角色 — 只请求该角色有权访问的数据 */
      await sharedStore.loadFromServer(authStore.user?.role ?? null)
    } catch {
      /* 加载失败不阻塞 */
    }
  }
})

/* 监听 http 拦截器触发的登出事件（401 刷新失败等）：
 * 必须真正清空会话与共享数据，而不是「恢复」——
 * 否则内存里会残留上一位用户的数据。 */
window.addEventListener('auth:logout', () => {
  authStore.clearSession()
})
</script>

<template>
  <RouterView />
</template>
