/**
 * 写入操作 API — 所有写操作（创建、更新、删除、状态切换、文件上传/下载）封装
 *
 * 模块路由策略（Frontend Integration）：
 *   - v2（/api/v2/，requestV2）：
 *     User/Student/Teacher/Admin 档案（api/urls.py + api/views/*），
 *     以及已迁移的业务模块 applications / assignments / announcements /
 *     system / academic-years / teachers(quotas) —— 见 api/urls.py 的 v2 业务路由，
 *     与 v1 共享同一批 View/Service，因此 v1、v2 读到的业务状态天然一致。
 *   - v1（/api/v1/，request）：**尚未迁移**的模块
 *     imports（上传/模板/错误报告）；auth（登录/登出/刷新/me）按后端契约保留 v1。
 *
 * request.get/post/put/patch/delete 已自动解包 ApiResponse.data。
 * request.raw 用于文件上传/下载（绕过自动解包，返回原始数据）。
 *
 * v2 接口规范：
 *   - 路径风格：动作式（如 users/{id}/update、students/{id}/delete）
 *   - update 方法：PUT（非 PATCH）
 *   - Student/Teacher/Admin 用各自档案主键（student_id/teacher_id/admin_id），非 user_id
 *   - 创建用户/学生/导师/管理员：password 必填
 */
import { request, requestV2 } from './http'

/* ========== 1. 申请管理 ========== */

/** 学生提交申请的请求体 */
export interface SubmitApplicationBody {
  academic_year: number
  teacher: number
  round: number
}

/** 批量操作申请的请求体 */
export interface BatchApplicationBody {
  application_ids: number[]
}

/** 申请记录（后端返回） */
export interface ApplicationResult {
  id: number
  academic_year: number
  student: number
  teacher: number
  round: number
  status: number
  [key: string]: unknown
}

/**
 * 学生提交申请
 * 后端端点：POST applications/
 * @param body 申请参数（学年、导师、轮次）
 */
export function submitApplicationApi(body: SubmitApplicationBody): Promise<ApplicationResult> {
  return requestV2.post('applications/', body)
}

/**
 * 导师通过申请
 * 后端端点：POST applications/{id}/approve/
 * @param id 申请 ID
 */
export function approveApplicationApi(id: number): Promise<ApplicationResult> {
  return requestV2.post(`applications/${id}/approve/`)
}

/**
 * 导师拒绝申请
 * 后端端点：POST applications/{id}/reject/
 * @param id 申请 ID
 */
export function rejectApplicationApi(id: number): Promise<ApplicationResult> {
  return requestV2.post(`applications/${id}/reject/`)
}

/** 导师撤销第一轮已通过的录取；路径参数是申请 ID。 */
export function revokeApprovalApi(applicationId: number): Promise<ApplicationResult> {
  return requestV2.post(`applications/${applicationId}/revoke-approval/`)
}

/**
 * 批量通过申请
 * 后端端点：POST applications/batch-approve/
 * @param body 批量申请 ID 列表
 */
export function batchApproveApplicationApi(body: BatchApplicationBody): Promise<ApplicationResult[]> {
  return requestV2.post('applications/batch-approve/', body)
}

/**
 * 批量拒绝申请
 * 后端端点：POST applications/batch-reject/
 * @param body 批量申请 ID 列表
 */
export function batchRejectApplicationApi(body: BatchApplicationBody): Promise<ApplicationResult[]> {
  return requestV2.post('applications/batch-reject/', body)
}

/**
 * R3-06: 学生取消第二轮申请（释放名额）
 * 后端端点：POST applications/{id}/cancel/
 * @param id 申请 ID
 */
export function cancelApplicationApi(id: number): Promise<void> {
  return requestV2.post(`applications/${id}/cancel/`)
}

/* ========== 2. 系统状态 ========== */

/** 状态推进请求体 */
export interface StateForwardBody {
  academic_year: number
  reason?: string
}

/** 状态回退请求体 */
export interface StateRollbackBody {
  academic_year: number
  reason: string
}

/** 更新调度配置请求体 */
export interface UpdateScheduleBody {
  academic_year: number
  first_round_start_at?: string
  first_round_end_at?: string
  teacher_review_end_at?: string
  second_round_end_at?: string
  auto_enabled?: boolean
}

/** 启停自动切换请求体 */
export interface ToggleAutoScheduleBody {
  academic_year: number
  enabled: boolean
}

/**
 * 状态推进
 * 后端端点：POST system/states/forward/
 * @param body 推进参数（学年、可选原因）
 */
export function forwardStateApi(body: StateForwardBody): Promise<unknown> {
  return requestV2.post('system/states/forward/', body)
}

/**
 * 状态回退
 * 后端端点：POST system/states/rollback/
 * @param body 回退参数（学年、原因）
 */
export function rollbackStateApi(body: StateRollbackBody): Promise<unknown> {
  return requestV2.post('system/states/rollback/', body)
}

/**
 * 更新调度配置
 * 后端端点：PUT|PATCH system/schedules/update-by-year/
 * @param body 调度配置参数
 */
export function updateScheduleApi(body: UpdateScheduleBody): Promise<unknown> {
  return requestV2.put('system/schedules/update-by-year/', body)
}

/**
 * 启停自动切换
 * 后端端点：POST system/schedules/toggle-auto/
 * @param body 启停参数（学年、是否启用）
 */
export function toggleAutoScheduleApi(body: ToggleAutoScheduleBody): Promise<unknown> {
  return requestV2.post('system/schedules/toggle-auto/', body)
}

/* ========== 3. 公告管理 ========== */

/** 创建公告请求体 */
export interface CreateAnnouncementBody {
  academic_year: number
  title: string
  content: string
  is_published?: boolean
}

/** 更新公告请求体 */
export interface UpdateAnnouncementBody {
  title?: string
  content?: string
}

/** 公告记录（后端返回） */
export interface AnnouncementResult {
  id: number
  academic_year: number
  title: string
  content: string
  is_published: boolean
  [key: string]: unknown
}

/**
 * 创建公告
 * 后端端点：POST announcements/
 * @param body 公告参数
 */
export function createAnnouncementApi(body: CreateAnnouncementBody): Promise<AnnouncementResult> {
  return requestV2.post('announcements/', body)
}

/**
 * 更新公告
 * 后端端点：PATCH announcements/{id}/
 * @param id 公告 ID
 * @param body 更新字段
 */
export function updateAnnouncementApi(
  id: number,
  body: UpdateAnnouncementBody,
): Promise<unknown> {
  return requestV2.patch(`announcements/${id}/`, body)
}

/**
 * 发布公告
 * 后端端点：POST announcements/{id}/publish/
 * @param id 公告 ID
 */
export function publishAnnouncementApi(id: number): Promise<unknown> {
  return requestV2.post(`announcements/${id}/publish/`)
}

/**
 * 取消发布公告
 * 后端端点：POST announcements/{id}/unpublish/
 * @param id 公告 ID
 */
export function unpublishAnnouncementApi(id: number): Promise<unknown> {
  return requestV2.post(`announcements/${id}/unpublish/`)
}

/**
 * 删除公告
 * 后端端点：DELETE announcements/{id}/
 * @param id 公告 ID
 */
export function deleteAnnouncementApi(id: number): Promise<unknown> {
  return requestV2.delete(`announcements/${id}/`)
}

/* ========== 4. 学生管理（v2 — /api/v2/students/*） ========== */

/** 创建学生请求体 — v2 一次性创建 User + Student，password 必填 */
export interface CreateStudentBody {
  username: string
  password: string
  student_number: string
  name: string
  major: string
  class_name: string
  department?: string
  phone?: string
}

/** 更新学生请求体 — v2 不允许修改 student_number、user_id */
export interface UpdateStudentBody {
  name?: string
  major?: string
  class_name?: string
  department?: string
}

/** 更新学生电话请求体 — v2 学生自助修改 */
export interface UpdateStudentPhoneBody {
  phone: string
}

/**
 * 创建学生（同时创建 User 和 Student）
 * v2 端点：POST /api/v2/students/create
 * @param body 学生信息（含 username/password）
 */
export function createStudentApi(body: CreateStudentBody): Promise<unknown> {
  return requestV2.post('students/create', body)
}

/**
 * 更新学生信息
 * v2 端点：PUT /api/v2/students/{student_id}/update
 * @param studentId 学生档案 ID（v2 student_id，非 user_id）
 * @param body 更新字段
 */
export function updateStudentApi(studentId: number, body: UpdateStudentBody): Promise<unknown> {
  return requestV2.put(`students/${studentId}/update`, body)
}

/**
 * 更新学生电话（学生自助修改）
 * v2 端点：PUT /api/v2/students/{student_id}/phone
 * @param studentId 学生档案 ID
 * @param body 电话字段
 */
export function updateStudentPhoneApi(studentId: number, body: UpdateStudentPhoneBody): Promise<unknown> {
  return requestV2.put(`students/${studentId}/phone`, body)
}

/**
 * 删除学生
 * v2 端点：DELETE /api/v2/students/{student_id}/delete
 * @param studentId 学生档案 ID（v2 student_id，非 user_id）
 */
export function deleteStudentApi(studentId: number): Promise<unknown> {
  return requestV2.delete(`students/${studentId}/delete`)
}

/* ========== 5. 导师管理（v2 — /api/v2/teachers/*） ========== */

/** 创建导师请求体 — v2 一次性创建 User + Teacher，password 必填 */
export interface CreateTeacherBody {
  username: string
  password: string
  teacher_number: string
  name: string
  college: string
  title?: string
  research_area?: string
  profile?: string
  graduation_direction?: string
  thesis_topic?: string
  student_requirement?: string
}

/** 更新导师请求体 — v2 不允许修改 teacher_number、user_id */
export interface UpdateTeacherBody {
  name?: string
  college?: string
  title?: string
  research_area?: string
  profile?: string
  graduation_direction?: string
  thesis_topic?: string
  student_requirement?: string
}

/** 设置单个名额请求体 */
export interface UpdateQuotaBody {
  max_quota: number
}

/** 单条名额配置 */
export interface QuotaItem {
  teacher_id: number
  max_quota: number
}

/** 批量设置名额请求体 */
export interface BatchQuotaBody {
  academic_year: number
  quotas: QuotaItem[]
}

/**
 * 创建导师（同时创建 User 和 Teacher）
 * v2 端点：POST /api/v2/teachers/create
 * @param body 导师信息（含 username/password）
 */
export function createTeacherApi(body: CreateTeacherBody): Promise<unknown> {
  return requestV2.post('teachers/create', body)
}

/**
 * 更新导师信息
 * v2 端点：PUT /api/v2/teachers/{teacher_id}/update
 * @param teacherId 导师档案 ID（v2 teacher_id，非 user_id）
 * @param body 更新字段
 */
export function updateTeacherApi(teacherId: number, body: UpdateTeacherBody): Promise<unknown> {
  return requestV2.put(`teachers/${teacherId}/update`, body)
}

/**
 * 删除导师
 * v2 端点：DELETE /api/v2/teachers/{teacher_id}/delete
 * @param teacherId 导师档案 ID（v2 teacher_id，非 user_id）
 */
export function deleteTeacherApi(teacherId: number): Promise<unknown> {
  return requestV2.delete(`teachers/${teacherId}/delete`)
}

/**
 * 设置单个名额
 * v2 端点：PATCH /api/v2/teachers/quotas/{id}/（TeacherQuotaViewSet，仅管理员）
 * @param id 名额记录 ID
 * @param body 名额参数
 */
export function updateQuotaApi(id: number, body: UpdateQuotaBody): Promise<unknown> {
  return requestV2.patch(`teachers/quotas/${id}/`, body)
}

/**
 * 批量设置名额
 * v2 端点：POST /api/v2/teachers/quotas/batch/（仅管理员）
 * @param body 批量名额配置
 */
export function batchSetQuotaApi(body: BatchQuotaBody): Promise<unknown> {
  return requestV2.post('teachers/quotas/batch/', body)
}

/* ========== 6. 分配管理 ========== */

/** 自动分配预览请求体 */
export interface AutoAssignPreviewBody {
  academic_year: number
}

/** 执行自动分配请求体 */
export interface AutoAssignRunBody {
  academic_year: number
  dry_run?: boolean
}

/** 撤销自动分配请求体 */
export interface AutoAssignRevokeBody {
  academic_year: number
  auto_assignment_log: number
}

/** 自动分配执行结果 */
export interface AutoAssignRunResult {
  log_id: number
  total_unassigned: number
  assigned_count: number
  failed_count: number
  is_dry_run: boolean
  is_all_assigned: boolean
  [key: string]: unknown
}

/** 撤销自动分配结果 */
export interface AutoAssignRevokeResult {
  revoked_count: number
  log_id: number
}

/** 录取记录（后端 AdmissionSerializer 返回） */
export interface AdmissionResult {
  id: number
  academic_year: number
  student: number
  teacher: number
  source: number
  application: number | null
  auto_assignment_log: number | null
  created_at: string
  [key: string]: unknown
}

/**
 * 自动分配预览
 * 后端端点：POST assignments/auto-assign/preview/
 * @param body 预览参数（学年）
 */
export function previewAutoAssignApi(body: AutoAssignPreviewBody): Promise<Record<string, unknown>> {
  return requestV2.post('assignments/auto-assign/preview/', body)
}

/**
 * 执行自动分配
 * 后端端点：POST assignments/auto-assign/run/
 * @param body 执行参数（学年、可选 dry_run）
 */
export function runAutoAssignApi(body: AutoAssignRunBody): Promise<AutoAssignRunResult> {
  return requestV2.post('assignments/auto-assign/run/', body)
}

/**
 * 撤销自动分配
 * 后端端点：POST assignments/auto-assign/revoke/
 * @param body 撤销参数（学年、自动分配日志 ID）
 */
export function revokeAutoAssignApi(body: AutoAssignRevokeBody): Promise<AutoAssignRevokeResult> {
  return requestV2.post('assignments/auto-assign/revoke/', body)
}

/** 管理员人工分配请求体 — 学生/导师均为 canonical user_id */
export interface ManualAssignBody {
  academic_year: number
  /** 学生 canonical user_id */
  student: number
  /** 导师 canonical user_id */
  teacher: number
}

/**
 * 管理员人工分配（持久化到 admission 表）
 *
 * v2 端点：POST /api/v2/assignments/manual-assign/（权限 IsAdmin，成功返回 201）
 *
 * 名额权威在服务端：本接口不做任何本地「乐观成功」，
 * 调用方必须在成功后重新拉取录取列表与导师汇总名额（directory）。
 *
 * @param body 分配参数（学年、学生 user_id、导师 user_id）
 */
export function manualAssignApi(body: ManualAssignBody): Promise<AdmissionResult> {
  return requestV2.post('assignments/manual-assign/', body)
}

/* ========== 7. 学年管理 ========== */

/** 创建学年请求体 */
export interface CreateAcademicYearBody {
  name: string
  start_year: number
  end_year: number
}

/** 更新学年请求体 */
export interface UpdateAcademicYearBody {
  name?: string
  start_year?: number
  end_year?: number
}

/**
 * 创建学年
 * v2 端点：POST /api/v2/academic-years/
 * @param body 学年信息
 */
export function createAcademicYearApi(body: CreateAcademicYearBody): Promise<unknown> {
  return requestV2.post('academic-years/', body)
}

/**
 * 更新学年
 * v2 端点：PATCH /api/v2/academic-years/{id}/
 * @param id 学年 ID
 * @param body 更新字段
 */
export function updateAcademicYearApi(
  id: number,
  body: UpdateAcademicYearBody,
): Promise<unknown> {
  return requestV2.patch(`academic-years/${id}/`, body)
}

/**
 * 激活学年
 * v2 端点：POST /api/v2/academic-years/{id}/activate/
 * @param id 学年 ID
 */
export function activateAcademicYearApi(id: number): Promise<unknown> {
  return requestV2.post(`academic-years/${id}/activate/`)
}

/**
 * 关闭学年
 * v2 端点：POST /api/v2/academic-years/{id}/close/
 * @param id 学年 ID
 */
export function closeAcademicYearApi(id: number): Promise<unknown> {
  return requestV2.post(`academic-years/${id}/close/`)
}

/**
 * 删除学年
 * v2 端点：DELETE /api/v2/academic-years/{id}/
 * @param id 学年 ID
 */
export function deleteAcademicYearApi(id: number): Promise<unknown> {
  return requestV2.delete(`academic-years/${id}/`)
}

/* ========== 8. 用户管理（v2 — /api/v2/users/*） ========== */

/** 创建用户请求体 — v2 password 必填 */
export interface CreateUserBody {
  username: string
  password: string
  role: number
}

/** v2 创建用户响应 */
export interface CreateUserResult {
  user_id: number
}

/** v2 用户记录 */
export interface UserResult {
  id: number
  username: string
  role: number
  status: number
  created_at: string
  updated_at: string
}

/** 更新用户请求体 — v2 仅允许修改 role、status */
export interface UpdateUserBody {
  role?: number
  status?: number
}

/** 重置密码请求体 — v2 管理员用 */
export interface ResetPasswordBody {
  new_password: string
}

/**
 * 创建用户
 * v2 端点：POST /api/v2/users/create
 * @param body 用户信息（含 password）
 */
export function createUserApi(body: CreateUserBody): Promise<CreateUserResult> {
  return requestV2.post('users/create', body)
}

/**
 * 更新用户（role/status）
 * v2 端点：PUT /api/v2/users/{user_id}/update
 * @param userId 用户 ID
 * @param body 更新字段
 */
export function updateUserApi(userId: number, body: UpdateUserBody): Promise<unknown> {
  return requestV2.put(`users/${userId}/update`, body)
}

/**
 * 删除用户
 * v2 端点：DELETE /api/v2/users/{user_id}/delete
 * @param userId 用户 ID
 */
export function deleteUserApi(userId: number): Promise<unknown> {
  return requestV2.delete(`users/${userId}/delete`)
}

/**
 * 禁用用户
 * v2 端点：PUT /api/v2/users/{user_id}/disable
 * @param userId 用户 ID
 */
export function disableUserApi(userId: number): Promise<unknown> {
  return requestV2.put(`users/${userId}/disable`)
}

/**
 * 启用用户
 * v2 端点：PUT /api/v2/users/{user_id}/enable
 * @param userId 用户 ID
 */
export function enableUserApi(userId: number): Promise<unknown> {
  return requestV2.put(`users/${userId}/enable`)
}

/**
 * 重置密码（管理员用，无需旧密码）
 * v2 端点：PUT /api/v2/users/{user_id}/reset_password
 * @param userId 用户 ID
 * @param body 新密码
 */
export function resetPasswordApi(userId: number, body: ResetPasswordBody): Promise<unknown> {
  return requestV2.put(`users/${userId}/reset_password`, body)
}

/* ========== 8.1 管理员管理（v2 — /api/v2/admins/*） ========== */

/** 创建管理员请求体 — v2 一次性创建 User + Admin，password 必填 */
export interface CreateAdminBody {
  username: string
  password: string
  name: string
}

/** 更新管理员请求体 — v2 仅允许修改 name */
export interface UpdateAdminBody {
  name?: string
}

/**
 * 创建管理员（同时创建 User 和 Admin）
 * v2 端点：POST /api/v2/admins/create
 * @param body 管理员信息（含 username/password/name）
 */
export function createAdminApi(body: CreateAdminBody): Promise<unknown> {
  return requestV2.post('admins/create', body)
}

/**
 * 更新管理员信息
 * v2 端点：PUT /api/v2/admins/{admin_id}/update
 * @param adminId 管理员档案 ID（v2 admin_id，非 user_id）
 * @param body 更新字段
 */
export function updateAdminApi(adminId: number, body: UpdateAdminBody): Promise<unknown> {
  return requestV2.put(`admins/${adminId}/update`, body)
}

/**
 * 删除管理员
 * v2 端点：DELETE /api/v2/admins/{admin_id}/delete
 * @param adminId 管理员档案 ID（v2 admin_id，非 user_id）
 */
export function deleteAdminApi(adminId: number): Promise<unknown> {
  return requestV2.delete(`admins/${adminId}/delete`)
}

/* ========== 9. Excel 导入 ========== */

/** 上传 Excel 请求参数 */
export interface UploadExcelParams {
  file: File
  role: number
  academic_year: number
}

/** 上传 Excel 任务响应 */
export interface UploadExcelResponse {
  task_id: string
  [key: string]: unknown
}

/**
 * 上传 Excel 文件
 * 后端端点：POST imports/upload/
 * Content-Type: multipart/form-data
 * @param params 上传参数（文件、角色、学年）
 */
export function uploadExcelApi(params: UploadExcelParams): Promise<UploadExcelResponse> {
  const formData = new FormData()
  formData.append('file', params.file)
  formData.append('role', String(params.role))
  formData.append('academic_year', String(params.academic_year))
  return request.raw.post('imports/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }) as unknown as Promise<UploadExcelResponse>
}

/**
 * 下载导入模板
 * 后端端点：GET imports/template/
 * 返回二进制流（Excel 文件）
 */
export function downloadImportTemplateApi(): Promise<Blob> {
  return request.raw.get('imports/template/', {
    responseType: 'blob',
  }) as unknown as Promise<Blob>
}

/**
 * 下载导入错误报告
 * 后端端点：GET imports/tasks/{task_id}/error-report/
 * 返回二进制流（Excel 文件）
 * @param taskId 导入任务 ID
 */
export function downloadImportErrorReportApi(taskId: string | number): Promise<Blob> {
  return request.raw.get(`imports/tasks/${taskId}/error-report/`, {
    responseType: 'blob',
  }) as unknown as Promise<Blob>
}
