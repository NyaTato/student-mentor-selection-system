/**
 * Axios HTTP 实例 + JWT 拦截器 + TraceID 传递
 *
 * - 请求拦截器：
 *   1. 注入 Authorization: Bearer <access>
 *   2. 自动生成并注入 X-Trace-ID（UUID v4，与后端 OpenTelemetry / Jaeger 链路追踪关联）
 * - 响应拦截器：
 *   1. 统一解包 ApiResponse { code, message, data }
 *   2. 401 自动刷新（refresh token），刷新失败则登出
 *   3. 403 提示无权限
 *   4. 业务错误（code !== 0）抛出 Error
 */
import axios, { type AxiosInstance, type AxiosPromise, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

/* TraceID Header 名称（与后端 TraceIDMiddleware 约定） */
const TRACE_HEADER = 'X-Trace-ID'

/**
 * 生成 UUID v4 格式的 TraceID
 *
 * 用于全链路追踪：前端 → Nginx → Django → Service → Repository → SQL/Redis → Celery → 日志 → Jaeger
 * 后端 TraceIDMiddleware 优先读取此 header，与 OpenTelemetry Span Context 协同工作
 */
function generateTraceId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // 兼容不支持 crypto.randomUUID 的环境
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/* 后端统一响应格式 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/**
 * HTTP 层错误 — 携带 status，供调用方区分「404 资源不存在」与「403 无权限」。
 *
 * 角色裁剪后的读取接口会返回 404（不可见即不存在）或 403（越权），
 * 二者的处理方式不同：404 可容忍，403 必须上抛，不能被静默吞掉。
 */
export class HttpError extends Error {
  readonly status?: number
  readonly code?: number

  constructor(message: string, status?: number, code?: number) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.code = code
  }
}

/** 从任意异常中提取 HTTP 状态码 */
export function errorStatus(err: unknown): number | undefined {
  return err instanceof HttpError ? err.status : undefined
}

/* 分页响应数据格式 */
export interface PaginatedData<T> {
  list: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/* Token 存储键
 * 使用 sessionStorage 而非 localStorage：每个浏览器标签页独立存储，
 * 避免同一浏览器多标签页登录不同角色时 token 相互覆盖（权限串扰）。
 * sessionStorage 刷新页面时保留，关闭标签页才销毁，符合多角色同时登录的需求。
 */
const ACCESS_TOKEN_KEY = 'mentor_access_token'
const REFRESH_TOKEN_KEY = 'mentor_refresh_token'

export const tokenStorage = {
  getAccess(): string | null {
    return sessionStorage.getItem(ACCESS_TOKEN_KEY)
  },
  getRefresh(): string | null {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY)
  },
  set(access: string, refresh: string) {
    sessionStorage.setItem(ACCESS_TOKEN_KEY, access)
    sessionStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clear() {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY)
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

/* 创建 Axios 实例（v1，默认） */
const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

/* 创建 Axios 实例（v2 — User/Student/Teacher/Admin 模块迁移用） */
const httpV2: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_V2_BASE_URL || '/api/v2',
  timeout: 15000,
})

/* 请求拦截器工厂 — 注入 Authorization + X-Trace-ID（v1/v2 共用） */
function applyRequestInterceptors(instance: AxiosInstance) {
  instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccess()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    /* 每个请求自动携带 TraceID，用于全链路追踪 */
    if (!config.headers[TRACE_HEADER]) {
      config.headers[TRACE_HEADER] = generateTraceId()
    }
    return config
  })
}

applyRequestInterceptors(http)
applyRequestInterceptors(httpV2)

/* 是否正在刷新 token */
let isRefreshing = false
/* 等待 token 刷新的请求队列 */
let pendingQueue: Array<(token: string | null) => void> = []

/* 刷新 token */
async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) return null
  try {
    /* 使用独立 axios 实例避免循环拦截 */
    const resp = await axios.post<ApiResponse<{ access: string; refresh: string }>>(
      '/api/v1/auth/refresh/',
      { refresh },
      { timeout: 10000 },
    )
    if (resp.data?.code === 0 && resp.data.data?.access) {
      const { access, refresh: newRefresh } = resp.data.data
      tokenStorage.set(access, newRefresh)
      return access
    }
    return null
  } catch {
    return null
  }
}

/* 触发登出（避免循环依赖，通过事件通知 auth store） */
function triggerLogout() {
  tokenStorage.clear()
  sessionStorage.removeItem('user')
  window.dispatchEvent(new CustomEvent('auth:logout'))
  /* 若不在登录页则跳转 */
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login'
  }
}

/* ElMessage 去重 — 短时间内相同的错误消息只弹一次，避免重复弹窗 */
let lastErrorMessage = ''
let lastErrorTime = 0
function showErrorMsg(msg: string) {
  const now = Date.now()
  if (msg === lastErrorMessage && now - lastErrorTime < 1000) {
    return /* 1秒内相同消息不重复显示 */
  }
  lastErrorMessage = msg
  lastErrorTime = now
  ElMessage.error(msg)
}

/* 从 DRF serializer.errors 中提取第一个字段错误消息
   后端返回格式: { "username": ["用户名只能..."], "phone": ["手机号格式..."] } */
function extractValidationError(data: unknown, fallback: string): string {
  if (data && typeof data === 'object') {
    const errors = data as Record<string, unknown>
    for (const key in errors) {
      const val = errors[key]
      if (Array.isArray(val) && val.length > 0 && typeof val[0] === 'string') {
        return val[0]
      }
      if (typeof val === 'string') {
        return val
      }
    }
  }
  return fallback
}

/* 响应拦截器工厂 — 解包 + 401 刷新 + 403 提示（v1/v2 共用） */
function applyResponseInterceptors(instance: AxiosInstance, replacer: (cfg: InternalAxiosRequestConfig) => AxiosPromise) {
  instance.interceptors.response.use(
    (response) => {
      /* 非标准 ApiResponse（如文件下载）直接返回 */
      const ct = String(response.headers['content-type'] ?? '')
      if (ct.includes('application/json')) {
        const body = response.data as ApiResponse
        if (body && typeof body.code === 'number') {
          if (body.code === 0) {
            /* 成功：返回 data 字段 */
            return body.data as unknown as never
          }
          /* 业务错误 — 优先从 serializer.errors 中提取字段级错误消息 */
          const errMsg = extractValidationError(body.data, body.message || '请求失败')
          showErrorMsg(errMsg)
          return Promise.reject(new HttpError(errMsg, response.status, body.code))
        }
      }
      return response.data
    },
    async (error) => {
      const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
      const status = error.response?.status

      /* 401 — 尝试刷新 token */
      if (status === 401 && original && !original._retry) {
        /* login 请求失败 — 直接显示后端错误消息（如"账号或密码错误"），不触发登出 */
        if (original.url?.includes('auth/login/')) {
          const msg = error.response?.data?.message || '账号或密码错误'
          showErrorMsg(msg)
          return Promise.reject(new HttpError(msg, status, error.response?.data?.code))
        }
        /* refresh 请求失败 — 直接触发登出 */
        if (original.url?.includes('auth/refresh/')) {
          triggerLogout()
          return Promise.reject(error)
        }

        if (isRefreshing) {
          /* 已在刷新中，排队等待 */
          return new Promise((resolve, reject) => {
            pendingQueue.push((token) => {
              if (!token) {
                reject(new Error('登录已过期'))
                return
              }
              original.headers!.Authorization = `Bearer ${token}`
              resolve(replacer(original))
            })
          })
        }

        original._retry = true
        isRefreshing = true
        const newToken = await refreshAccessToken()
        isRefreshing = false

        if (newToken) {
          /* 重放排队请求 */
          pendingQueue.forEach((cb) => cb(newToken))
          pendingQueue = []
          original.headers!.Authorization = `Bearer ${newToken}`
          return replacer(original)
        }

        /* 刷新失败 — 登出 */
        pendingQueue.forEach((cb) => cb(null))
        pendingQueue = []
        showErrorMsg('登录已过期，请重新登录')
        triggerLogout()
        return Promise.reject(new Error('登录已过期'))
      }

      /* 403 — 无权限提示 */
      if (status === 403) {
        showErrorMsg('您没有权限执行此操作')
        return Promise.reject(new HttpError('无权限', 403, error.response?.data?.code))
      }

      /* 其它错误 — 优先从 serializer.errors 中提取字段级错误消息 */
      const respData = error.response?.data
      const msg = extractValidationError(respData?.data, respData?.message || error.message || '网络错误')
      if (status !== 401) {
        showErrorMsg(msg)
      }
      return Promise.reject(new HttpError(msg, status, respData?.code))
    },
  )
}

/* 响应拦截器 — 解包 + 401 刷新 + 403 提示 */
applyResponseInterceptors(http, (cfg) => http(cfg))
applyResponseInterceptors(httpV2, (cfg) => httpV2(cfg))

/* 便捷方法 — 返回已解包的 data */
export const request = {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return http.get(url, config) as unknown as Promise<T>
  },
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return http.post(url, data, config) as unknown as Promise<T>
  },
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return http.put(url, data, config) as unknown as Promise<T>
  },
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return http.patch(url, data, config) as unknown as Promise<T>
  },
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return http.delete(url, config) as unknown as Promise<T>
  },
  /* 原始 axios 用于文件上传/下载（返回完整 response） */
  raw: http,
}

/* v2 便捷方法 — 用于 User/Student/Teacher/Admin 模块（baseURL=/api/v2） */
export const requestV2 = {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return httpV2.get(url, config) as unknown as Promise<T>
  },
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return httpV2.post(url, data, config) as unknown as Promise<T>
  },
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return httpV2.put(url, data, config) as unknown as Promise<T>
  },
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return httpV2.patch(url, data, config) as unknown as Promise<T>
  },
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return httpV2.delete(url, config) as unknown as Promise<T>
  },
  /* 原始 v2 axios 实例 */
  raw: httpV2,
}

export default http
