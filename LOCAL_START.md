# 本地固定配置与启动

日常使用统一入口：在项目根`G:\selflore`运行`start-local.cmd`，随后打开`http://127.0.0.1:24566`。前端构建和API由同一个进程提供，按Ctrl+C停止。

## 首次配置

已为本机准备`apps/api/.env`，保存固定开发连接参数；它被Git忽略，不包含密码。可提交的`apps/api/.env.example`仅作模板；启动脚本只在.env缺失时复制模板，不覆盖已有配置。

在本机PowerShell执行：

```powershell
Set-Location G:\selflore
.\start-local.cmd -Configure
```

按提示输入两次**PostgreSQL角色selflore_dev_app的既有密码**。它不是SelfLore登录密码，也不是selflore_dev_migrator密码。输入不显示字符，密码不进入命令历史；请勿在聊天发送。配置不会重设数据库密码，也不需要数据库在线。

应用密码保存在`.cache/local/pgpass.conf`，文件转义冒号和反斜杠；Windows凭据目录仅允许当前用户和SYSTEM读取，缓存不入Git或发布包。配置通过后无需每天输入密码。

若不知道app角色密码，应查找当初初始化记录，或由数据库管理员重设该角色密码；不能直接把迁移密码当成应用密码。

## 日常启动和检查

先启动本机已有PostgreSQL实例，确保6171监听。项目启动不会初始化数据库、创建表或执行迁移。

```powershell
# 只读核对连接、角色、PG18、业务表、权限和端口
.\start-local.cmd -CheckOnly

# 检查通过后，冻结同步依赖、构建前端并启动统一页面/API
.\start-local.cmd
```

需要已安装uv、pnpm及Node.js；首次依赖安装可能需要网络。脚本使用项目已有uv.lock与pnpm-lock.yaml，不更新锁文件。uv明确加载`apps/api/.env`，普通`uv run uvicorn`命令不会自动加载该文件。

配置允许的唯一目标是`127.0.0.1:6171/selflore_dev`，角色为`selflore_dev_app`；生产库或迁移角色在连接前拒绝。已有进程环境变量优先于.env，若被旧SELFLORE_DATABASE_URL或SELFLORE_ENV覆盖，会提示目标错误，需在启动终端清除旧值。迁移密码、PGPASSWORD和其他隐式libpq连接源在启动进程中清除，不改用户级环境变量。

## 常见问题

- 提示尚未配置应用密码：执行一次`-Configure`。
- 数据库连接失败：确认PostgreSQL已启动；密码错误时重新`-Configure`。
- 24566被占用：停止原有API后再启动，不会强行结束其他服务。
- 表或权限缺失：按[迁移说明](apps/api/CARD_MIGRATIONS.md)单独处理；启动不自动迁移。
- 页面使用更新源码：重新运行启动命令会重建前端。修改.env后重启生效。

开发热更新仍可使用Vite24567，但需先启动已加载.env的API。原有外部Start Tab配置本轮未修改，默认日常使用本文命令。

## 验证记录

2026-10-09：启动配置边界与认证设置测试22项通过；Windows真实ACL验证当前用户与SYSTEM两类访问；uv实际加载.env通过；缺少app凭据时固定启动入口安全停止。配置文件及凭据被Git忽略，现有发布包清单不会包含这两个位置。

用户完成密码配置后，实际`start-local.cmd -CheckOnly`通过：开发库app角色、PG18、业务表及24566端口符合预期。`start-local.cmd`冻结依赖同步、前端构建及真实服务启动成功；首页和/knowledge返回200，/api/health返回ok，/api/auth/config确认注册开启，未登录访问/auth/me和/me/profile返回401。未创建测试账号或写入用户内容。本机应用已运行，网页可访问；本轮仅完成启动验收，真实账号完整业务流程另行验收。

## 资料卡与媒体扩展

资料卡图片需要先追加0005迁移，再通过`start-local.cmd -ConfigureMedia -MediaRoot G:\selflore-data\media -OpsRoot G:\selflore-data\media-ops`初始化，并在`.env`设置两个对应媒体变量。`-CheckOnly`核对已配置目录身份与权限，普通启动不初始化目录。 详细步骤和限制见 [MEDIA_STORAGE.md](MEDIA_STORAGE.md)。
