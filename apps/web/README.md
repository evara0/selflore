# SelfLore Web

SelfLore 的 React 前端。产品功能和演示地址见[项目首页](../../README.md)；运行时版本要求以[依赖清单](package.json)和锁文件为准。

## 开发

先按[API 配置与运行](../api/AUTH_CONFIGURATION.md#2-开发运行示例)启动后端。以下命令在 `apps/web` 执行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

访问 `http://127.0.0.1:24567`，Vite 将 `/api` 转发到 `http://127.0.0.1:24566`。默认开发 Origin 使用 `127.0.0.1`；更换主机名或端口需同步配置后端。

## 检查与构建

```powershell
pnpm format:check
pnpm test
pnpm lint
pnpm build
```

`pnpm build` 先执行 TypeScript 构建检查，再输出 `dist/`。由 API 提供构建页面时，需要启动或重启 API；固定 Windows 一键启动见[本地启动](../../LOCAL_START.md)。

`pnpm format`使用锁定的Prettier统一`src`下TypeScript／TSX及前端根TS配置；`pnpm format:check`只检查、不写文件，仓库CI也执行此项。配置采用100列、单引号、无分号和LF，仓库的限定Git属性确保这些文件在Windows也检出为LF。Oxlint继续负责代码规则。CSS与浏览器测试不纳入本次格式整理。

`pnpm test:e2e` 使用本机 Chrome 和独立的24568测试服务，不能直接指向日常应用或演示站点。数据库、浏览器及视觉验收的准备步骤统一见[本地验证](../api/WORKSPACE_TESTING.md)。

## 代码入口

| 路径 | 职责 |
| --- | --- |
| `src/main.tsx`、`src/App.tsx` | 应用挂载、身份及认证控制状态 |
| `src/app/` | 页面框架、导航与路由；保留旧URL兼容入口 |
| `src/features/` | 卡片、备忘、合集、复习、个人资料及认证弹窗；统一卡片列表为`cards/Cards.tsx`，复习仍在`knowledge/Review.tsx` |
| `src/features/cards/Editor.tsx`、`CardForm.tsx`、`CardSources.tsx` | 按卡片类型选择编辑器、编辑状态与提交、受控的组织及来源区；合集编辑器在`collections/CollectionEditor.tsx` |
| `src/components/` | 共享展示、选择器和附件组件 |
| `src/lib/` | API 请求、类型、查询、演示数据与工具函数 |
| `src/*.test.tsx`、`e2e/` | 组件测试与真实浏览器测试 |

前端通过 API 读写本人内容，不直接连接数据库。游客数据由 `src/lib/demo.ts` 提供，修改它只改变示例，不修改账号的真实数据。
