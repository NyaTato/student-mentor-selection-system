# mentor-select-backend（简版指针）

Django 5 + DRF 后端。完整说明见根 `README.md` 与 `docs/ARCHITECTURE.md`、`docs/API.md`、
`docs/testing.md`、`docs/development.md`。

## 启动/测试（Windows 友好）

```bat
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements-tested.txt
copy .env.example .env
:: 将 .env 的 DJANGO_SETTINGS_MODULE 改为 config.settings.dev，并填写本机服务配置
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
python -m pytest apps api -q
```

灵活开发替代：`python -m pip install -r requirements-dev.txt`（仍受 `constraints-security.txt` 约束）。

隔离演示：先 `mkdir work`，再 `python manage.py migrate --settings=config.settings.demo`
→ `python manage.py seed_demo --settings=config.settings.demo [--password ...]`
→ `python manage.py runserver 127.0.0.1:8000 --settings=config.settings.demo`
（随机密码，只打印一次；详见根 README 与 `docs/development.md`）。

演示/测试账号不在此列出固定密码；演示密码按次随机，业务账号请用 `createsuperuser` 或 Excel 导入创建。

## License

MIT，Copyright (c) 2026 NyaTato，见 `LICENSE`。
