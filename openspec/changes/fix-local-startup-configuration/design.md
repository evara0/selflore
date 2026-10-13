## Context

API的Settings仅读取进程变量；uv支持--env-file，现有前端构建可由API在同一端口提供。本次沿用这些能力，避免给生产应用加入隐式本地配置读取。

## Goals / Non-Goals

**Goals:** 一次安全配置后直接启动；连接固定dev/app角色；启动失败可诊断；配置和密码不会输出或入Git。

**Non-Goals:** 不修改外部Start Tab、注册策略、数据库或服务器；不自动运行迁移或数据库初始化；不代用户设置未知密码。

## Decisions

1. apps/api/.env保存无密码连接参数与PGPASSFILE相对位置，.env.example可提交。root start-local.cmd调用PowerShell启动入口，uv --env-file显式注入，已有进程变量若覆盖则必须通过目标检查。
2. app.local_start提供--configure和--check；configure使用隐藏输入确认，libpq密码文件转义冒号与反斜杠，写入.cache/local并限制Windows ACL。密码不用聊天、参数或.env字符串传递；文件只允许当前用户和SYSTEM读取，原有配置不覆盖。
3. 预检仅允许127.0.0.1:6171/selflore_dev/selflore_dev_app和PG18，只读核对业务表权限；验证不读取迁移账本。启动构建Web后在24566提供统一页面和API，前台运行Ctrl+C停止。开发热更新仍可单独运行24567。
4. launcher创建缺失.env但不覆盖已有文件，使用项目缓存和冻结依赖；运行进程不继承迁移密码或PGPASSWORD。启动不连接生产、不建表。

## Risks / Trade-offs

密码文件是本机明文凭据 → 单独ACL、Git忽略、发布包不包含缓存；不输出文件内容。

预检成功不等于端口持续可用 → 服务启动仍检查占用；冲突时明确停止，不终止已有服务。

## Migration Plan

无需数据库迁移。用户运行start-local.cmd -Configure输入既有app密码，再运行start-local.cmd；-CheckOnly用于诊断。原有命令继续有效，外部Start Tab若要使用新入口另行更新。
