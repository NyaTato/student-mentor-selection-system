# 本地开发与演示

## 1. 全新复现（Windows 友好）

```bat
:: 后端（精确复现）
cd mentor-select-backend
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements-tested.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

:: 后端测试
python -m pytest apps api -q

:: 前端
cd mentor-select-frontend
npm ci
copy .env.example .env.local
npm run dev
npm run build
```

前端经 Vite 代理或 Nginx 反代访问 `/api/v1`、`/api/v2`；跨域直连后端时
`.env.local` 设 `VITE_API_BASE_URL=http://localhost:8000/api/v1`
（v2 基地址默认 `/api/v2`，见 `src/api/http.ts`）。

## 2. 环境变量

- 后端示例：`mentor-select-backend/.env.example`；前端示例：`mentor-select-frontend/.env.example`；
根示例：根 `.env.example`（仅开发本地端点 + 空密码 + 占位密钥；生产示例明确不可直接使用）。
- 生产密钥由运维自行随机生成（`SECRET_KEY` ≥50 位、`JWT_SIGNING_KEY` 显式设置时 ≥32 位，
不含 `change-me/example/insecure/default/password/todo/xxxx` 等标记），`prod.py` 启动即校验，
不合规直接拒绝启动。不要把任何真实 `.env` 提交入库。

## 3. 隔离演示（故意降级，不可用于生产）

```bat
cd mentor-select-backend
mkdir work
python manage.py migrate --settings=config.settings.demo
python manage.py seed_demo --settings=config.settings.demo [--password 自设密码]
python manage.py runserver 127.0.0.1:8000 --settings=config.settings.demo
```

隔离点（见 `config/settings/demo.py`）：SQLite 固定 `<backend>/work/demo.sqlite3`；
`CACHES` 为 LocMemCache；Celery eager + `memory://`；原生 Redis 指向不可用端口
`127.0.0.1:1/DB15`（需真 Redis 的自动推进/自动分配在演示中不可用，属设计取舍）；
`SECRET_KEY` 仅取 `DEMO_SECRET_KEY` 或按进程随机，`SIMPLE_JWT.SIGNING_KEY` 回指演示密钥；
`DEBUG=False`；`ALLOWED_HOSTS` 仅 localhost/127.0.0.1/testserver；CORS 仅放行本地 3000 端口。
请勿以 `0.0.0.0` 对外暴露演示。

种子（`apps/common/management/commands/seed_demo.py`，幂等 `update_or_create`）：
`demo_admin`、`demo_teacher/demo_teacher2`、`demo_student/demo_student2/demo_student3`；
学年 `2026-2027`（ACTIVE）、两位导师各名额 2、一则已发布公告；不播种申请/录取。
密码经 `--password` / `SMSP_DEMO_PASSWORD` 传入，均未提供则按进程随机
`secrets.token_urlsafe(16)`，只打印一次，不写文件、无硬编码密码。

## 4. 旧库说明（无自动迁移）

旧实现曾写 legacy `student/teacher/admin/user` 表并手工同步档案；现 canonical 单写后
不再读写 legacy 表，**不提供旧生产库自动迁移**。历史数据需按 `user_id` 离线对账后导入新库；
`seed_demo` 与测试夹具均只写 canonical 模型。`model/entity`、`model/sql` 保留为纯归档。
