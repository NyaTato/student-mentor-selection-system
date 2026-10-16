import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { type UserInfo, UserRole } from '@/types'
import { loginApi, logoutApi } from '@/api/auth'
import { tokenStorage } from '@/api/http'
import { useSharedStore } from './shared'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserInfo | null>(null)
  const token = ref<string>('')

  /**
   * 清空共享 store 中的角色数据。
   *
   * 跨账号隐私边界：登录、登出、以及 401 强制下线时都必须清空，
   * 否则上一个账号（例如管理员）的数据会留在内存里被下一位用户看到。
   * 调用点都在运行时（非模块求值期），因此与 shared store 的互相引用是安全的。
   */
  function clearSharedData() {
    useSharedStore().clear()
  }

  const isAuthenticated = computed(() => !!token.value)
  const userRole = computed(() => user.value?.role || '')

  /* 角色对应的首页路径 — router guard 与 LoginView 共用的单一映射源 */
  const homePath = computed(() => {
    switch (user.value?.role) {
      case UserRole.STUDENT:
        return '/student/dashboard'
      case UserRole.TEACHER:
        return '/teacher/dashboard'
      case UserRole.ADMIN:
        return '/admin/dashboard'
      default:
        return '/login'
    }
  })

  /* 登录 — 调用真实 JWT API
   * token 与 user 存入 sessionStorage（每标签页独立），避免多标签页登录不同角色时相互覆盖。
   * 登录成功后清空共享 store：换账号 / 换角色时不得保留上一位用户的数据。
   */
  async function login(username: string, password: string): Promise<UserInfo> {
    const { access, refresh, user: userInfo } = await loginApi(username, password)
    user.value = userInfo
    token.value = access
    tokenStorage.set(access, refresh)
    sessionStorage.setItem('user', JSON.stringify(userInfo))
    clearSharedData()
    return userInfo
  }

  /* 清除本地会话（token + 用户 + 共享数据）— 不做任何网络请求 */
  function clearSession() {
    user.value = null
    token.value = ''
    tokenStorage.clear()
    sessionStorage.removeItem('user')
    clearSharedData()
  }

  /* 登出 — 调用后端黑名单 refresh token */
  async function logout() {
    const refresh = tokenStorage.getRefresh()
    if (refresh) {
      try {
        await logoutApi(refresh)
      } catch {
        /* 登出失败不阻塞前端清理 */
      }
    }
    clearSession()
  }

  /* 从 sessionStorage 恢复会话（每标签页独立，刷新页面保留，关闭标签页销毁） */
  function restore() {
    const savedToken = tokenStorage.getAccess()
    const savedUser = sessionStorage.getItem('user')
    if (savedToken && savedUser) {
      token.value = savedToken
      try {
        user.value = JSON.parse(savedUser) as UserInfo
      } catch {
        user.value = null
        token.value = ''
        tokenStorage.clear()
      }
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    userRole,
    homePath,
    login,
    logout,
    clearSession,
    restore,
  }
})
