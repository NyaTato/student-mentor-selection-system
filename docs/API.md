# 学生选导师系统 API（v2 现状，以路由源码为准）

> 路由真相：`mentor-select-backend/config/urls.py` 挂载 `api/v1/ → config.api_urls`、`api/v2/ → api.urls`。
> 下表按源码分类；“路由复用”指同一 View 被 v1/v2 同时 include，不是重写两套功能。

## 1. v2 状态表

| 组 | 范围 | 说明 |
|---|---|---|
| A 已完成 v2（重建功能） | `api/urls.py`：`users/*`（login/list/create/{id}/update/change_password/reset_password/disable/enable/delete）、`students/*`（list/create/{id}/by_user/by_number/update/phone/delete）、`teachers/*`、`admins/*` | canonical ORM 重写；响应形状保持；权限收紧（改他人密码 403、用户/管理员列表仅管理员、学生 phone 字段级可见） |
| B 仍只 v1 | `imports/*`（upload/template/tasks/error-report/logs）、`logs/*`（operation/login）；`auth/*`（login/refresh/logout/me/change-password）按后端契约保留 v1 | 前端经 v1 调用（见 `src/api/data-loader.ts`、`write-api.ts` 头注释） |
| C 路由复用（v1 兼容 + v2 正式） | `applications/`（CRUD/my/teacher/approve/reject/batch-approve/batch-reject/cancel/**revoke-approval**）、`assignments/`（admissions/auto-logs/**manual-assign**/auto-assign/preview+run+revoke）、`announcements/`、`system/`（states/schedules/histories）、`statistics/`、`academic-years/`、`teachers/`（profiles/directory/quotas） | `api/urls.py` 与 `config/api_urls.py` include 同一套 `apps.*.urls`；v1/v2 同 View 同数据。`manual-assign/` 在 v1 是兼容别名；`revoke-approval/` 路径参数是申请 ID |
| D 旧归档 | `model/entity/*.py（managed=False）` 等；原项目的 `model/sql/*.sql` 不纳入公开副本 | 无业务引用，不参与运行 |

前端：`requestV2` 走 `/api/v2`（档案 + 已迁移业务），`request` 走 `/api/v1`（imports/logs/auth 等）。名额展示唯一可信源是汇总接口 `teachers/profiles/directory/`（`max_quota/admitted_count/remaining_quota/has_quota`），不得用裁剪后的录取列表自行 count。

## 2. 认证与权限

JWT Bearer（SimpleJWT，HS256）。`POST /api/v1/auth/login/` → `{access, refresh}`；401 拦截器自动刷新；`refresh` 真轮换 + 旧 token 黑名单；禁用/软删账号刷新 401，缺字段 400。登出将 refresh 加入黑名单（Redis）。权限：默认 `IsAuthenticated` 叠加 `IsStudent/IsTeacher/IsAdmin` + 数据级 queryset 裁剪 + 系统状态联动。

## 3. 统一响应/分页/错误

- 成功：`{"code": 0, "message": "...", "data": ...}`（`ApiResponse`，见 `apps/common/response.py`）。
- 分页：`data = {"list": [], "total": n, "page": p, "page_size": s, "total_pages": t}`（`StandardPageNumberPagination`，`page_size` 最大 100；前端 `getList/getListV2` 有界翻全页，不截断）。
- HTTP：200 查询/更新/删除（含删除保留响应体）、201 创建（含 `manual-assign`）、400 参数/业务、401 未认证、403 无权限、404 不存在（含越权整行不可见）、409 冲突、429 限流、500 系统错误。
- 错误码：v2 档案层小码 `0/1001–1005/10001`（`constant/error_code.py`）；v1 业务层分段码 `1xxxx（通用）/2xxxx 用户/3xxxx 学生/4xxxx 导师（含 40003 QUOTA_NOT_FOUND）/5xxxx 申请/6xxxx 分配（含 60001 ADMISSION_NOT_FOUND、60003 配额满）/7xxxx 公告/8xxxx 学年/9xxxx 系统状态/10xxxx 导入/11xxxx 日志`。非法查询参数统一 400（`apps/common/query_params.py`，QueryDict 归一化后缺省保持缺省）。
- 时间：`Asia/Shanghai`，`USE_TZ=True`，DRF 默认 ISO-8601。
- ID 契约：canonical 档案主键 = `user_id`；v2 `id == user_id`；旧 legacy 自增 `id` 不可混用。

## 4. 常用端点速查

- 健康：`GET /api/v1/health/` → `{"status": "ok"}`。
- 文档（仅非生产开放，生产 `SERVE_INCLUDE_SCHEMA=False` 不注册）：`/api/schema/`、`/api/docs/`。
- 档案 v2：见上表 A 组（动作式路径，update 用 PUT）。
- 申请：`POST applications/`（学生；第二轮未配置名额拒绝）、`POST applications/{id}/approve|reject/`（导师；`TEACHER_REVIEW` 内）、`POST applications/{id}/revoke-approval/`（撤销第一轮录取）、`POST applications/{id}/cancel/`（学生取消第二轮，精确释放）。
- 分配：`POST assignments/manual-assign/`（管理员，201）、`POST assignments/auto-assign/preview|run|revoke/`（管理员）、`GET assignments/admissions/`、`GET assignments/auto-logs/`（仅管理员）。
- 公告：非管理员强制只见已发布（含显式 `?is_published=false` 也不可见草稿）。
- 统计/学年/系统：查询参数非法值 400；`system/schedules/toggle-auto` 等写操作仅管理员。

旧版长端点表如与上表冲突，以本文件与路由源码为准。
