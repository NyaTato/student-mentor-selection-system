# 面试问答要点（与实现一致，不夸大）

## 为什么名额不能用 Redis 计数？

MySQL REPEATABLE READ 下普通 `SELECT COUNT` 会复用事务快照，即使持有名额行锁也会读到过期计数
导致超卖。实现用 `select_for_update()` 物化后 `len()` 做当前读 + 固定锁顺序 + `uk_year_student`
兜底；Redis 锁只是辅助降冲突。`cache_service.py` 的业务读缓存当前未被生产 Service 调用，
所以不声称 Redis 读缓存一致性。

## v1/v2 是两套功能吗？

不是。档案 CRUD 是 v2 重建（canonical ORM）；业务模块是路由复用——`api/urls.py` 与
`config/api_urls.py` include 同一套 `apps.*.urls`，v1/v2 同 View 同数据。`imports/logs/auth`
仍只 v1。旧 `model/entity + model/sql` 是纯归档。

## JWT 刷新是真轮换吗？

是。`AuthService.refresh_token` 先做缺字段 400 与账号可用性 401 检查，再委托 SimpleJWT
`TokenRefreshSerializer`，`ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION` 真生效；
旧 refresh 用后 401。

## 越权读取返回什么？

整行不可见即 404（`total` 与行同过滤），越权写 403。前端只请求当前角色有权数据，
容忍 404（资源尚不存在），403 一律上抛（见 `data-loader.ts` 头注释与 `HttpError`）。

## 旧生产库怎么迁？

不自动迁。旧 legacy 表不再读写，历史数据按 `user_id` 离线对账后导入 canonical；
新部署直接 `migrate` 空库即可。
