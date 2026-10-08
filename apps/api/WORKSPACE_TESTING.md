# 本地验证与隔离测试

## 常规检查

在 `apps/api` 执行 `uv sync --frozen`、`uv run pytest -q`；未提供隔离 DSN 时，数据库集成测试会明确 skip，不能视为通过。前端在 `apps/web` 执行 `pnpm install --frozen-lockfile`、`pnpm test`、`pnpm lint`、`pnpm build`。

Vitest 使用 threads / 单 worker，规避本机 Windows 子进程 IPC 限制。浏览器测试位于 `apps/web/e2e`，使用本机 Chrome；API 24568 提供同次前端构建产物。Playwright 不依赖远端服务。

## 完整数据库测试

测试夹具会清空身份和业务表，**只允许自行准备的一次性6179实例**，禁止使用6171开发库或生产库。迁移演练额外核对 PostgreSQL data_directory 位于本项目 `.cache/card-tests`。实例 / 角色先用 `app.db_bootstrap` 建立，再用 `app.db_migrate` 应用全链；不要把这种测试配置带到实际环境。

在 PowerShell 的 `apps/api` 配置：

```powershell
$env:SELFLORE_TEST_ISOLATED = '1'
$env:SELFLORE_TEST_APP_DSN = 'host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app'
$env:SELFLORE_TEST_MIGRATOR_DSN = 'host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_migrator'
uv run pytest -q -p no:cacheprovider --basetemp ../../.cache/card-tests/full-run
```

示例 DSN 未含密码，若实例需要密码，使用本机凭据设施。测试包含真实事务 / 并发请求 / FK / 增量迁移演练；不接受改端口来复用实际业务数据库。

## 浏览器闭环

先执行 `pnpm build`。随后在 `apps/api` 的专用终端配置：

```powershell
$env:SELFLORE_DATABASE_URL = $env:SELFLORE_TEST_APP_DSN
$env:SELFLORE_ENV = 'dev'
$env:SELFLORE_ALLOW_REGISTRATION = 'true'
$env:SELFLORE_ALLOWED_ORIGINS = 'http://127.0.0.1:24568'
uv run uvicorn app.main:app --host 127.0.0.1 --port 24568 --no-access-log
```

在另一终端的 `apps/web` 设置 SELFLORE_TEST_ISOLATED=1，执行 `pnpm test:e2e`。浏览器测试会创建隔离私有账号与样例，通过真实界面创建知识 / 观点 / 合集、评分、改稿冲突、浏览器返回提示、随机顺序、填空揭示、网络失败重试和退出缓存隔离。不能与后端清理测试并行运行。

实际截图保存到 `docs/design/card-navigation-v1/implemented`；追踪失败文件在 `.cache/card-tests/browser-results`。千卡检索 EXPLAIN 存为该截图目录的 `search-explain.json`，短中文搜索可能选择 owner/更新顺序 B-tree；pg_trgm 对短于3字符的查询不承诺强制走 GIN。

浏览器服务 Ctrl+C 停止。一次性 PG 用本机 pg_ctl 指定该 `.cache/card-tests/pgdata` 目录执行 `-m fast -w stop`；停止后保留或按需清理缓存，不触及业务库。

## 发布检查

`deploy\publish.cmd -CheckOnly` 不连接服务器；可使用相同隔离 DSN 运行完整数据库检查。`deploy/tests/remote-gate.sh` 用临时目录和替身命令验证暂存后仍无 current、无成功迁移标记无法激活。实际生产迁移和探针仍需在正式发布时授权执行。
