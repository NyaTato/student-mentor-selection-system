<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Reading, User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: '',
  password: '',
})

const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!form.username || !form.password) {
    errorMsg.value = '请输入学号/工号和密码'
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    await authStore.login(form.username, form.password)
    router.push(authStore.homePath)
  } catch (err) {
    errorMsg.value = (err as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo"><el-icon :size="48"><Reading /></el-icon></div>
        <h1 class="login-title">学生选导师系统</h1>
        <p class="login-subtitle">导师双选平台</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label class="form-label">学号 / 工号</label>
          <el-input
            v-model="form.username"
            class="login-input"
            placeholder="请输入学号 / 工号"
            :prefix-icon="User"
          />
        </div>

        <div class="form-field">
          <label class="form-label">密码</label>
          <el-input
            v-model="form.password"
            class="login-input"
            type="password"
            show-password
            placeholder="请输入密码"
            :prefix-icon="Lock"
            @keyup.enter="handleLogin"
          />
        </div>

        <p v-if="errorMsg" class="form-error">{{ errorMsg }}</p>

        <button type="submit" :disabled="loading" class="login-btn">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <div class="login-links">
          <a href="#" class="login-link">忘记密码</a>
          <span class="login-link-divider">|</span>
          <a href="#" class="login-link">重置密码</a>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background: var(--color-canvas);
}

.login-card {
  width: 420px;
  background: var(--color-card);
  border-radius: var(--rounded-xl);
  border: 1px solid var(--color-hairline);
  box-shadow: var(--shadow-card);
  padding: var(--spacing-xl);
}

.login-header {
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.login-logo {
  color: var(--color-primary);
  margin-bottom: var(--spacing-sm);
}

.login-title {
  font-size: var(--text-headline);
  font-weight: var(--text-headline-weight);
  color: var(--color-ink);
  margin-bottom: var(--spacing-xs);
}

.login-subtitle {
  font-size: var(--text-body-sm);
  color: var(--color-ink-subtle);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-muted);
}

/* el-input — 白底 + 灰边框 + Focus 蓝色描边 */
.login-input :deep(.el-input__wrapper) {
  background: var(--color-card);
  border: 1px solid var(--color-hairline);
  border-radius: var(--rounded-md);
  box-shadow: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.login-input :deep(.el-input__wrapper:hover) {
  border-color: var(--color-hairline-strong);
}

.login-input :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.login-input :deep(.el-input__inner) {
  color: var(--color-ink);
  font-size: var(--text-body);
}

.login-input :deep(.el-input__inner::placeholder) {
  color: var(--color-ink-subtle);
}

.form-error {
  color: var(--color-semantic-error);
  font-size: var(--text-caption);
}

/* Login button — 蓝色渐变 */
.login-btn {
  width: 100%;
  margin-top: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-md);
  border-radius: var(--rounded-md);
  border: none;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-hover) 100%);
  color: var(--color-surface-1);
  font-size: var(--text-button);
  font-weight: var(--text-button-weight);
  cursor: pointer;
  transition: opacity 0.15s;
}

.login-btn:hover {
  opacity: 0.9;
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-links {
  display: flex;
  justify-content: center;
  gap: var(--spacing-sm);
  font-size: var(--text-caption);
}

.login-link {
  color: var(--color-ink-subtle);
  text-decoration: none;
}

.login-link:hover {
  color: var(--color-primary);
}

.login-link-divider {
  color: var(--color-hairline-strong);
}
</style>
