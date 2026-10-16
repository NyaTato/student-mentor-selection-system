# 第三方依赖许可证清单（仅标识，不构成法律意见）

> 来源：发布前本地包元数据快照，仅用于标识许可证名称；该审查文件含本机路径，未随公开仓库发布。
> 依赖的许可证各自独立适用，不归属本项目作者；本项目代码为 MIT（Copyright (c) 2026 NyaTato）。
> 下列版本号为该元数据快照时记录，不代表当前冻结验证版本（如 Python 补丁运行时已升至
> Django 5.2.18 / DRF 3.18.3 等，见 `docs/testing.md`）。

## 前端（npm，`mentor-select-frontend/package.json` 直接依赖及传递闭包）

- MIT（绝大多数，含 `vue`、`vue-router`、`pinia`、`axios`、`element-plus`、
`@element-plus/icons-vue`、`vite`、`@vitejs/plugin-vue`、`unocss` 系列、`typescript` 工具链、
`eslint` 及插件、`vue-tsc` 等）：按各自 `LICENSE` 使用。
- Apache-2.0（`@eslint/config-array`、`@eslint/config-helpers`、`@eslint/core`、
`@eslint/object-schema`、`@eslint/plugin-kit`、`typescript` 等，及若干 `eslint-visitor-keys`）。
- BSD-2-Clause / BSD-3-Clause（`entities`、`eslint-scope`、`espree`、`esquery`、
`esrecurse`、`estraverse`、`esutils`、`normalize-wheel-es`、`source-map-js`、`speakingurl` 等）。
- ISC（`boolbase`、`flatted`、`glob-parent`、`isexe`、`picocolors`、`semver`、`which`）。
- MPL-2.0（`lightningcss` 及其平台包）。
- CC0-1.0（`mdn-data`）、0BSD（`tslib`）、BlueOak-1.0.0（`minimatch`）。
- 完整逐包许可证以锁文件解析的包元数据及各依赖包附带的许可证文本为准；此处不逐条复制 300+ 条目。

## 后端（Python，元数据快照节选）

- BSD-3-Clause：`Django`、`djangorestframework`、`celery`、`python-dotenv`。
- MIT：`djangorestframework-simplejwt`、`redis`、`openpyxl`。
- Apache：`django-prometheus`（元数据记为 `Apache`）。
- GPL-2.0-or-later：`mysqlclient`（链路例外不展开；按其许可证使用，不要静态混淆声明）。

## Vite 默认素材

公开副本只保留新绘制的几何 `favicon.svg`，不包含来源不明或未使用的旧图标。
