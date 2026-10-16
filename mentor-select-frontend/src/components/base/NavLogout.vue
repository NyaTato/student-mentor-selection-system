<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const router = useRouter()

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <button class="nav-logout" @click="handleLogout">退出登录</button>
</template>

<style scoped>
.nav-logout {
  display: flex;
  align-items: center;
  width: 100%;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--rounded-sm);
  border: none;
  background: transparent;
  color: var(--color-ink-subtle);
  font-size: var(--text-body-sm);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.nav-logout:hover {
  background: var(--color-error-bg);
  color: var(--color-semantic-error);
}
</style>
