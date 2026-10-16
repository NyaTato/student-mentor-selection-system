/**
 * 认证 API — 登录、登出、刷新、当前用户、修改密码
 *
 * 登录/登出/刷新/获取当前用户：保留 v1（/api/v1/auth/xxx/）
 *   - v2 没有 logout/refresh/me 接口
 *   - v2 login 不返回 JWT token，会破坏前端 JWT 流程
 *
 * 修改密码：迁移到 v2（/api/v2/users/{user_id}/change_password）
 *   - v2 接口路径：PUT /api/v2/users/{user_id}/change_password
 *   - v2 参数：{ old_password, new_password }
 *
 * 对应后端：
 *   v1: apps/users/urls_auth.py
 *     POST /api/v1/auth/login/
 *     POST /api/v1/auth/logout/
 *     POST /api/v1/auth/refresh/
 *     GET  /api/v1/auth/me/
 *   v2: api/urls.py + api/user_view.py
 *     PUT  /api/v2/users/{user_id}/change_password
 */
import { request, requestV2 } from './http'
import { mapUserRole } from './enum-mapper'
import { UserRole, type UserInfo } from '@/types'

/* 后端登录响应 */
interface LoginResponse {
  access: string
  refresh: string
  user: {
    id: number
    username: string
    role: number
    role_display: string
    status: number
    status_display: string
  }
}

/* 后端当前用户响应 */
interface UserProfileResponse {
  id: number
  username: string
  role: number
  role_display: string
  status: number
  status_display: string
  date_joined: string
  is_active: boolean
  student_profile: {
    student_number: string
    name: string
    major: string
    class_name: string
  } | null
  teacher_profile: {
    teacher_number: string
    name: string
    college: string
    title: string
    research_area: string
  } | null
  admin_profile: {
    name: string
  } | null
}

/* 登录 */
export async function loginApi(username: string, password: string): Promise<{
  access: string
  refresh: string
  user: UserInfo
}> {
  const data = await request.post<LoginResponse>('auth/login/', { username, password })
  const role = mapUserRole(data.user.role)
  /* 根据 role 和 profile 推导显示名 */
  let name = data.user.username
  if (role === UserRole.ADMIN && data.user.role_display) {
    name = data.user.role_display === '管理员' ? '系统管理员' : data.user.username
  }
  return {
    access: data.access,
    refresh: data.refresh,
    user: {
      id: data.user.id,
      username: data.user.username,
      name,
      role,
    },
  }
}

/* 登出 */
export async function logoutApi(refresh: string): Promise<void> {
  await request.post('auth/logout/', { refresh })
}

/* 获取当前用户完整信息 */
export async function getMeApi(): Promise<UserProfileResponse> {
  return request.get<UserProfileResponse>('auth/me/')
}

/* 修改密码 — v2 接口：PUT /api/v2/users/{user_id}/change_password */
export async function changePasswordApi(
  userId: number,
  oldPassword: string,
  newPassword: string,
): Promise<void> {
  await requestV2.put(`users/${userId}/change_password`, {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
