# 测试说明（只写证据内事实）

> 以下是 2026-10-16 在隔离测试环境运行的结果；详见私有执行记录。演示浏览器流程与 MySQL 并发测试分别验证，不把 SQLite 演示当成分布式 Redis 验证。

## 1. 后端（补丁验证运行时）

运行时：由 `requirements-tested.txt` 冻结的 82 包闭包（Django 5.2.18 / DRF 3.18.3 / PyJWT 2.15.1 /
idna 3.20 / sqlparse 0.6.0 / urllib3 2.8.0）。精确复现安装：

```bat
cd mentor-select-backend
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements-tested.txt
```

灵活开发替代：`python -m pip install -r requirements-dev.txt`（仍受 `constraints-security.txt`
下限 `PyJWT>=2.15.0 / sqlparse>=0.6.0 / idna>=3.15 / urllib3>=2.8.0` 约束）。不要安装审计运行时
（`work/audit-runtime` 仅是本地 `pip-audit` 工具载体），不要复制原已损坏 venv。

| 套件 | 证据结论 |
|---|---|
| SQLite 全量（`config.settings.test`） | 808 passed、6 MySQL-only skipped（814 collected，9.35s）；`makemigrations --check --dry-run` 无变更 |
| MySQL 全量（全新一次性 `test_smsp_*` 库） | 814 passed，28.24s，含 6 个严格并发测试 |
| 并发专项（`test_admission_concurrency.py`） | MySQL 下 6 passed（末座争抢、同学生重复分配、无名额、配额下调、第二轮末座、取消后重占）；SQLite 下显式 skip（无行锁、快照语义不同，不声称验证） |

MySQL 回归必须显式 opt-in（见 `config/settings/test_mysql.py`）：

```bat
set SMSP_ALLOW_ISOLATED_MYSQL_TESTS=1
set SMSP_TEST_DATABASE=test_smsp_<8-40位小写字母数字下划线>
```

Django 只创建/销毁该命名的测试库，不迁移、不触碰业务库；凭据只放本机环境/未跟踪 `.env`，
报告中不记录。`SMSP_TEST_DATABASE` 非 `test_smsp_*` 或未 opt-in 即拒绝启动。

## 2. 依赖安全（已验证部分）

- Python：初审 82 包闭包 37 advisories / 6 包（Django 5.2.16、DRF 3.17.1、idna 3.11、PyJWT 2.13.0、
sqlparse 0.5.5、urllib3 2.6.3）；已纠正 minima + `constraints-security.txt` + 冻结
`requirements-tested.txt`；终态 `pip-audit` 补丁闭包 0 已知漏洞（原始报告为私有 `work/` 下文件，不公开）。
- 前端：`npm audit --omit=dev` 旧 6 high 条目，在 semver 内修复；`npm ci --ignore-scripts` 后审计
0 vulnerabilities（280 包）。复现用 `npm ci`，不要用 `npm install` 改锁文件。

## 3. 前端、浏览器与隔离演示

- `npm run build`（vue-tsc + Vite）最终重跑通过；构建包含 TS 检查。`npm ci --ignore-scripts` 后审计为 0 vulnerabilities。
- 隔离演示：全新 SQLite 库迁移、`seed_demo` 重复执行表数量不变、非 demo settings 守卫拒绝写入。
- 本地真实浏览器按学生、导师、管理员三角色操作：第一轮学生提交并修改志愿；导师拒绝、通过并撤销已通过录取；第二轮申请即时占座、取消后释放、重新申请；管理员给未匹配学生人工分配；刷新页面后状态保留。截图为虚构演示数据，见 `screenshots/`。
- 演示刻意不连接真实 Redis，因此浏览器流程不覆盖 Redis 分布式锁/后台任务。最后名额与重复录取由上述独立 MySQL 并发测试验证。没有宣称线上部署或负载测试。
