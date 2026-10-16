# mentor-select-frontend（简版指针）

Vue 3 + TypeScript + Vite 前端。完整说明见根 `README.md` 与 `docs/ARCHITECTURE.md`、
`docs/API.md`、`docs/development.md`。

## 启动/构建

```bat
npm ci
copy .env.example .env.local
npm run dev
npm run build
npm run preview
npm run lint
```

API 基地址经 `VITE_API_BASE_URL`（默认 `/api/v1`，v2 默认 `/api/v2`，见 `src/api/http.ts`）。
测试/演示账号不在此列出固定密码；演示密码由后端 `seed_demo` 按次随机生成。

## License

MIT，Copyright (c) 2026 NyaTato，见 `LICENSE`。
