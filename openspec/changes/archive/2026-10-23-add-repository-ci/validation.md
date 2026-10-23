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

用户已明确授权提交推送并验证首次CI，同时同步此前已提交的文档整理。`7474bc8`已推送到origin/main，文档整理`34141bb`同时同步。

- [首次运行38870791632](https://github.com/evara0/selflore/actions/runs/38870791632)：docs通过；frontend的65项通过、2项账户测试失败；backend完成PGDG安装及冻结依赖安装，pg_ctl启动6179失败，尚未运行pytest。首次CI未通过，不能以本机结果替代。
- 已通过用户现有Chrome登录会话的正常GitHub页面读取日志；没有提取凭据。前端错误为找不到账户页的管理按钮／新密码字段，旧入口`/knowledge`重定向与账户导航存在竞态，会员用例还在懒加载后同步查询字段。改用当前`/cards`入口并等待字段出现，保留原有功能断言。
- 后端临时实例显式设置`unix_socket_directories = ''`，所有客户端继续使用127.0.0.1 TCP，避免依赖PGDG编译时的系统socket目录权限；仅在启动失败时输出有长度限制的本次启动日志。参见[PG18连接配置](https://www.postgresql.org/docs/18/runtime-config-connection.html#GUC-UNIX-SOCKET-DIRECTORIES)。
- 修复后的本机复测：13项辅助测试、85处文档链接、actionlint及Lint通过，67项前端Vitest通过；后端156项通过、0跳过，两个自有实例均已停止，报告`backend-39b087e62abf4bf183730ab8d941baa1.json`。
- 修复提交`81079489cbef3bd4684f67b4ab0a31bf95d73079`的[第二次运行38872441561](https://github.com/evara0/selflore/actions/runs/38872441561)三个job全部success：docs（116879475799）、frontend（116879475243）、backend（116879475664）。已通过公开GitHub API逐项核对依赖安装、辅助检查、组件测试、构建、PGDG安装、完整后端运行及报告上传步骤均成功；这是真实Ubuntu runner结果。
- OpenSpec严格验证与diff检查通过。CI及修复已提交推送；原有App.css与inline-mobile-builder-credit未纳入提交，没有改生产配置、分支保护或执行部署。所有任务已完成，保留变更未归档。

## 验证边界

本次无产品展示变化，浏览器截图及实际视觉审查不适用。基础CI不执行Playwright、生产备份或部署；未改分支保护。CI结果不替代既有人工视觉审查及本机发布门禁。

官方参考：[GitHub工作流](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)、[uv集成](https://docs.astral.sh/uv/guides/integration/github/)、[PostgreSQL Ubuntu安装](https://www.postgresql.org/download/linux/ubuntu/)。
