## Why

现有测试与发布门禁只在维护者本机运行，推送和PR不会自动产生仓库检查结果。用户要求配置仓库级自动CI，让公开协作能够复跑基础检查并明确失败和覆盖范围。

## What Changes

- 增加GitHub Actions工作流，push、pull_request和手动触发，使用只读权限、固定Action提交和并发取消。
- 三类独立检查：公开文档本地链接与CI辅助脚本测试；前端冻结安装、Lint、Vitest和TypeScript／Vite构建；后端冻结安装及现有完整pytest。
- 后端在runner内自行创建仅回环可用的6179和6180 PostgreSQL 18空实例，沿用现有夹具边界，结束或失败时停止所属实例，拒绝跳过或零测试的假通过。
- 增加可本地复跑的文档检查与后端CI辅助脚本，记录报告并更新公共验证说明。
- 不配置自动部署、生产连接、Secrets或仓库分支保护；浏览器E2E、视觉审查及私有发布检查继续按现有流程执行。

## Capabilities

### New Capabilities

- `repository-ci`: 仓库事件自动检查、隔离测试环境、失败及证据边界。

### Modified Capabilities

无。

## Impact

新增 `.github/workflows/ci.yml`、项目脚本与测试，更新README和测试说明。本地运行使用既有uv虚拟环境，不新增应用依赖；不修改业务源码或迁移SQL，保留现有未提交的CSS和独立变更。
