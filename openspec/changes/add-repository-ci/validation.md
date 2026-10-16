# 仓库CI验收

日期：2026-10-16。输入基线 `34141bb`；保留原有App.css及inline-mobile-builder-credit工作区修改。本次不修改业务源码、SQL或生产配置。

## 配置与本地验证

- `.github/workflows/ci.yml` 包含push、pull_request和workflow_dispatch，以及docs、frontend、backend三个独立job；contents只读、Action完整SHA固定、checkout不持久化凭据，并发取消旧运行。
- Action摘要由官方仓库对应版本的git ls-remote解析；uv固定0.11.16、Python3.13、Node22、pnpm取项目packageManager，PG18源按官方PGDG说明配置。
- actionlint1.7.12官方发布包SHA-256校验后执行，workflow语法与表达式通过；9段run命令经Git Bash的bash -n解析通过。
- 辅助脚本13项单元测试通过，覆盖缺文件／锚点、未跟踪及越界目标、图片和引用式链接、代码块／标题边界、端口占用、继承连接清理、部分启动失败及清理失败、JUnit跳过／空结果／错误拒绝。
- 文档检查85个本地链接通过，不访问外站，不扫描历史OpenSpec工件。
- 前端pnpm10.33.0冻结安装、Lint、67项Vitest和TypeScript／Vite构建均通过。首次非交互安装因本机缺少CI变量触发确认保护，设置与GitHub相同的CI=true后冻结安装通过，锁文件未变。
- 新后端CI入口在本机实际创建自有6179、6180 PG18实例：156项pytest通过，failed=0、skipped=0，owned_clusters_stopped=true。报告为本机忽略目录 `.cache/ci-reports/backend-67f4121186b34f6bb8aa3b97f57edae3.json` 及同名XML，前端报告为 `.cache/ci-reports/frontend.xml`。
- 后端存在两条上游弃用提示；前端既有网络错误用例产生React NaN提示，测试均通过。本次没有扩大为业务修复。
- 既有125个非Markdown／非OpenSpec文件摘要仍为 `7acbcb068ebbca6d628777435d24b60d4735e8b2ac8493ccabd2c0baf54edaa0`；原有工作区修改未纳入本次提交范围。

## 实际GitHub验证

用户已明确授权提交推送并验证首次CI，同时同步此前已提交的文档整理。实际GitHub运行尚待推送后观察；不能将上述本机Windows结果当作Ubuntu runner和PGDG安装已通过。

## 验证边界

本次无产品展示变化，浏览器截图及实际视觉审查不适用。基础CI不执行Playwright、生产备份或部署；未改分支保护。CI结果不替代既有人工视觉审查及本机发布门禁。

官方参考：[GitHub工作流](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)、[uv集成](https://docs.astral.sh/uv/guides/integration/github/)、[PostgreSQL Ubuntu安装](https://www.postgresql.org/download/linux/ubuntu/)。
