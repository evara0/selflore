# Windows 固定配置与启动

本文负责固定的一键启动流程。所有命令在仓库根目录的 PowerShell 执行，不要求仓库位于某个盘符；通用手动 API 配置见[认证配置](../apps/api/AUTH_CONFIGURATION.md#2-开发运行示例)。

## 首次准备与配置

先安装[README 中列出的依赖](../README.md#本地运行)，按[数据库初始化](../apps/api/DATABASE_SETUP.md)准备 PostgreSQL 18、开发角色和完整迁移链。固定入口只接受 `127.0.0.1:6171/selflore_dev`，应用角色为 `selflore_dev_app`；初始化示例中的5432需替换为6171。

```powershell
.\start-local.cmd -Configure
```

按提示输入两次 **selflore_dev_app 的既有数据库密码**，不是网站账号或迁移角色密码。输入隐藏，配置不会重设角色密码。缺少该密码时由数据库管理员核对或重设，不要用迁移密码替代。

脚本在 `apps/api/.env` 不存在时从 `.env.example` 复制模板，不覆盖已有文件。非秘密连接参数保存在 `.env`，应用密码单独保存在 `.cache/local/pgpass.conf`；Windows凭据目录仅允许当前用户和SYSTEM访问，两者均被Git忽略。

## 日常启动和停止

先启动已配置的PostgreSQL实例，再执行：

```powershell
# 只读核对连接、角色、PG18、业务表、权限和端口
.\start-local.cmd -CheckOnly

# 冻结同步依赖、构建前端，并启动统一页面／API
.\start-local.cmd
```

访问 `http://127.0.0.1:24566`，按 `Ctrl+C` 停止；重新执行启动命令会重建页面并启动API。启动不会安装数据库、建表或迁移；升级结构按[增量迁移](../apps/api/CARD_MIGRATIONS.md)单独执行。

启动入口通过 uv `--env-file` 显式加载 `.env`，依赖使用现有锁文件。当前终端的环境变量优先；旧 `SELFLORE_DATABASE_URL` 或 `SELFLORE_ENV` 会导致目标检查失败。脚本只清理自身进程中的迁移密码、PGPASSWORD和其他隐式连接源，不改用户级变量。

## 可选图片与热更新

- 图片上传：按[媒体配置](MEDIA_STORAGE.md#本机启用)初始化代码目录外的私有目录，再设置媒体环境变量；普通启动不会创建媒体目录。
- 前端热更新：按[手动运行说明](../apps/api/AUTH_CONFIGURATION.md#2-开发运行示例)启动API，再按[前端开发说明](../apps/web/README.md#开发)启动Vite24567。

## 常见问题

| 表现 | 先检查 |
| --- | --- |
| 应用密码未配置／密码错误 | 重新执行 `-Configure`，确认是app角色密码 |
| 数据库连接失败 | PostgreSQL是否监听6171、目标库及环境是否正确 |
| 24566被占用 | 停止原有API；脚本不会强行结束其他服务 |
| 表或权限缺失 | 先备份，再单独执行完整迁移；不要靠重启修复结构 |
| 页面仍旧／环境配置未生效 | 停止后重新启动，确认当前终端没有旧环境变量覆盖 |

`/api/health` 正常仅表示HTTP服务可用；登录后本人业务查询才能确认业务连接。测试与验收方法见[本地验证](../apps/api/WORKSPACE_TESTING.md)，本机历史验收不作为新环境前提。
