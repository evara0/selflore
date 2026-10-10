## Archive Review

用户已于 2026-10-10 完成验收，并授权下一步归档与 Git 提交。选定变更为 show-registration-rules-and-validation，schema 为 spec-driven；全部 4 项规划工件存在，7/7 实施任务完成。

已同步 registration-policy 的 5 项新增要求：简短规则展示、字段校验反馈、可解释提交状态、提示可访问性与窄屏适配、简化账号凭据规则。原有默认公开注册、显式关闭及注册安全要求保持不变。同步后逐项核对 delta 与主规格一致，严格校验通过。

验收证据见 validation.md：51 项前端测试、4 项浏览器测试、82 项后端常规测试通过；相关临时数据库迁移与真实账号流程的 2 项测试单独通过，其他需要隔离环境的 33 项后端测试未执行。lint、类型检查和构建通过。

新增 0004_relax_username.sql，历史迁移未改动。发布仍需先执行新增迁移，再更新后端与前端；归档和本地 Git 提交不代表生产发布。

本次仅提交该注册变更。已有的本地启动、数据库备份及其他文档改动保持未暂存；AUTH_CONFIGURATION.md 仅纳入账号规则和迁移说明部分。截图保留在被项目忽略的 docs/design/registration-feedback-v2，不强制加入 Git。
