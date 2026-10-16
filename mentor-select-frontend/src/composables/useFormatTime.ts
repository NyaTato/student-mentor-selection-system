/**
 * 时间格式化 Composable
 * 统一全项目的时间格式化逻辑，消除各视图重复定义的 formatTime / formatDateTime
 *
 * 输入兼容：
 *   - v2 表：Unix Timestamp 秒（数字或纯数字字符串，如 1784472086 / "1784472086"）
 *   - v1 表：ISO 8601 字符串（如 "2026-07-19T11:52:40" / "2026-07-19 11:52:40"）
 */

/**
 * 将任意时间值转换为 Date 对象
 * - 数字 / 纯数字字符串 → 视为 Unix Timestamp（秒），需 ×1000 转毫秒
 * - 其他字符串 → ISO 8601 解析（容错：将空格替换为 T，避免 Safari 等浏览器解析失败）
 */
function toDate(value: string | number): Date {
  if (typeof value === 'number') {
    return new Date(value * 1000)
  }
  if (/^\d+$/.test(value)) {
    return new Date(parseInt(value, 10) * 1000)
  }
  /* ISO 字符串：将空格替换为 T 以兼容 Safari/旧浏览器 */
  return new Date(value.replace(' ', 'T'))
}

/** 完整日期时间（年/月/日 时:分），undefined → '—' */
export function formatDateTime(iso?: string | number): string {
  if (!iso && iso !== 0) return '—'
  const date = toDate(iso)
  if (isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 简短日期时间（月/日 时:分，不含年份）— 用于最近操作等紧凑展示 */
export function formatTimeShort(iso: string | number): string {
  const date = toDate(iso)
  if (isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 含秒的完整日期时间 — 用于日志、实时时钟 */
export function formatTimeWithSeconds(value: Date | string | number): string {
  const date = value instanceof Date ? value : toDate(value)
  if (isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function useFormatTime() {
  return { formatDateTime, formatTimeShort, formatTimeWithSeconds }
}
