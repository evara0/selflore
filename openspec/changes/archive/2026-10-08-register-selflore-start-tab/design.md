## Context

见 `proposal.md`。Start Tab 当前配置位于 `G:\start-tab\StartTabData\config.json`，运行时的 `mergeConfig` 会保留非默认服务。项目已有 API 虚拟环境、Web 依赖和固定端口；Vite 将 `/api` 代理到 24566。

## Goals / Non-Goals

**Goals:** 注册两个本地启动项及一个组合，沿用项目现有可执行环境和端口。

**Non-Goals:** 不修改 SelfLore 应用代码、Start Tab 程序源码、其他服务或自动开机设置。

## Decisions

### 两个服务与一个组合

API 使用 `apps/api/.venv/Scripts/python.exe -m uvicorn app.main:app`；Web 使用现有 `pnpm.CMD run dev` 并指定 127.0.0.1、24567 和 `--strictPort`。Web 依赖 API，组合按 API → Web 顺序列出。相较于只启动 API 并依赖已有的 `dist`，两个服务能显示当前 Web 源码且不会要求每次先构建。

Web 的 `args` 在 `dev` 后直接传 `--host` 等参数，不插入独立的 `--`。当前 pnpm 会把独立的 `--` 原样交给 Vite，导致 Vite 忽略后面的主机参数并默认显示 `localhost`；Start Tab 对 `127.0.0.1` 的端口检测因此超时。

### 状态与地址

两个服务均以各自端口作为主要状态判定；API 额外检查 `/api/health`。打开地址分别使用 API 文档和 Web 首页。服务 ID 使用 `selflore-api`、`selflore-web`，组合 ID 为 `selflore-stack`，不与现有配置重复。

### 安全更新

分别通过 `register-service.js` 先预览再应用。先注册 API，再注册 Web 与组合。脚本在每次应用前保存带时间戳的配置备份。

## Risks / Trade-offs

- [24566 与“课笺”重合] → 保留既有 SelfLore 端口；两者不能同时启动，不修改“课笺”配置。
- [本地环境或依赖被删除] → 当前可执行路径存在；日后需重新安装环境后才能正常启动。
- [运行中的 Start Tab 未自动读取配置] → 更新后重启 Start Tab 或重新加载配置。

## Migration Plan

1. 预览两个服务和组合的配置变更。
2. 应用注册并核对新增 ID、端口、依赖及原有配置未变。
3. 如需回退，使用脚本生成的最新备份恢复配置。
