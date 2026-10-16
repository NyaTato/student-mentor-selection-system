# 简历项目描述（只写已验证事实）

**学生选导师系统**｜Vue 3 + TS + Vite × Django 5 + DRF + MySQL 8 + Redis + JWT｜2026

- 双轮双选闭环：第一轮填报可改、导师审核、可撤销；第二轮先到先得、精确取消；管理员人工分配与自动分配（预览/执行/撤销）；状态机推进/回滚。
- 并发正确性：固定锁顺序（学生→申请→名额→录取当前读）+ MySQL 行锁与唯一约束；6 个严格并发测试在一次性
MySQL 库通过；SQLite 全量 808 passed / 6 跳过、MySQL 全量 814 passed（2026-10-16 证据，见 `docs/testing.md`）。
- 安全收紧：档案整行级角色裁剪、学生 phone 字段级可见、改他人密码 403、JWT 真轮换+黑名单、生产密钥启动校验。
- 依赖安全：Python 82 包冻结闭包 `pip-audit` 0 已知漏洞；前端 semver 内修复后 `npm audit` 0 vulnerabilities。
- 隔离演示：`config.settings.demo` + 幂等 `seed_demo`（随机密码），SQLite/LocMem/不可用 Redis 端口，与生产完全隔离。

隔离虚构数据完成三角色浏览器核心流程，覆盖第一轮修改、导师审核/撤销、第二轮申请/取消、管理员人工分配及刷新后持久化；不宣称真实 Redis 的浏览器 E2E 或线上部署。
