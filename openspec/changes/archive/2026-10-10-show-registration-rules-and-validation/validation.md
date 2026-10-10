## Result

第二版简化注册规则和界面已完成。本地验收通过，已于 2026-10-10 经用户确认归档；生产尚未发布。第一版截图保留供比较，本报告以第二版为准。

## Accepted Behavior

- 用户名为 3–32 位，支持常用中文、英文字母、数字、下划线和连字符，不限制首字符；大小写不敏感唯一性保留。
- 密码最低长度改为 8，最大 128；登录、管理员创建账号、初始化管理员及修改密码使用一致规则，旧账号兼容。
- 常驻文字只有“3–32 位，支持中文”和“至少 8 位”。确认密码无额外常驻说明。
- 字段错误替代该字段帮助文字，删除底部重复汇总；保留失焦反馈、即时修正、描述关联和提交保护。

## Checks

前端命令在 apps/web 执行：

- pnpm test：4 个文件、51 项通过。
- pnpm lint：通过。
- pnpm build：类型检查和生产构建通过。
- pnpm exec playwright test e2e/registration.spec.ts：4 项通过，视口为 1280×800、390×844、320×568、390×400。

后端命令在 apps/api，使用既有 .venv：

- python -m pytest tests/test_registration_policy.py tests/test_auth_settings.py -q：31 项通过。
- SELFLORE_POLICY_TEST_ISOLATED=1 python -m pytest tests/test_registration_policy_db.py -q：2 项通过。
- python -m pytest -q：82 项通过，33 项因未配置各自所需的隔离数据库环境跳过，跳过项不视为通过。与本修订直接相关的真实数据库验证已单独执行。

额外检查：OpenSpec 严格校验、git diff --check 均通过；git diff --exit-code 确认 0001、0002、0003 历史迁移未修改。

## Database Rehearsal

新建 PostgreSQL 18 临时实例，仅监听 127.0.0.1:6180，数据位于本项目 .cache/registration-policy/run-846d5eff457049fbad1fff9d3d2d14da/pgdata。未连接开发或生产库执行迁移。验证后已停止临时数据库和临时前端服务。

演练先应用 0001 并建立旧账号，再通过实际迁移器执行完整增量链，包含 0004_relax_username，验证重跑无需重复迁移、旧账号 ID 和密码哈希保持不变。真实数据库确认中文及数字开头等用户名可插入，非法字符、长度越界和重复用户名仍被拒绝。

TestClient 使用真实数据库完成旧账号登录、中文和数字开头账号配合 8 位密码的注册登录，以及修改为 8 位新密码后重新登录。浏览器场景使用模拟 API 验证界面交互，没有创建线上测试账号。

## Visual Review

第二版 8 张截图位于 G:\selflore\docs\design\registration-feedback-v2。已检查移动端有效表单、桌面错误和 320px 错误状态：每个字段只有一条说明，没有重复汇总，文案更短；较矮视口仍支持纵向滚动，操作可到达且无横向溢出。

代表截图：390x844-valid.png、1280x800-errors.png、320x568-errors.png。截图目录沿用项目现有 docs 忽略规则。

## Notes

- 新增测试最初未限定管理员创建表单，匹配到了隐藏的登录字段；已限定表单范围并验证通过。
- 既有游客页面首次懒加载偶发超出默认 1 秒等待；已对该异步查询设置 5 秒等待，保留原断言。等待参数的一处类型错误已修正，最终完整测试和构建通过。
- 后端测试有既有 TestClient/httpx 与 anyio 弃用警告；本修订未更换依赖。
- 密码 Unicode 非基本字符的前后端计数差异沿用现有行为，服务端仍作最终校验。
- 账号配置说明已同步。发布时需先执行 0004_relax_username.sql，再更新后端与前端；本次没有对实际环境执行迁移或发布。
- 开始本次修订前已有的其他工作区修改保持原样。