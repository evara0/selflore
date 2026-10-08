# OpenSpec 变更整理记录

日期：2026-10-08。

## 当前完成状态

`build-card-knowledge-workspace` 已完成44/44项，并于2026-10-08按用户要求归档。归档核查时发现的15.1已在后续实施完成：移动底栏中央新建复用正式创建和游客登录提示，320/390/600px居中、触控、实际滚动固定和四导航可达性已通过浏览器验收。两个OpenSpec根当前均无待实施变更。

该change的七项业务能力均已同步到主规格；此前暂缓的card-workspace规格已在中央新建完成后同步。

## 本轮归档

整理阶段归档主项目12项、本地部署5项，后续完成并归档工作区1项，共新增18项归档。既有2026-09-22 Git初始化归档保持原内容。主项目共14项、本地部署共5项，合计19项归档历史；本地部署仍被Git忽略。

| 主项目变更 | 处理 |
| --- | --- |
| bootstrap-vite-web-shell | 用户确认旧视觉/占位设计已被正式四页取代，历史归档，不同步旧delta |
| refine-web-shell-typography | 旧原型布局被重做，历史归档，不同步旧delta |
| add-mobile-bottom-navigation | 旧Lattice/760px/五项底栏已被取代；正式中央新建仍保留在工作区待办 |
| add-create-navigation-and-auth-dialog | 真实认证与正式新建已替代原型；历史归档，不同步无后端约束 |
| bootstrap-fastapi-health-service | 健康检查独立性已实现，修正与后续业务端点的边界并同步 |
| bootstrap-postgresql-databases | 初始化、角色、幂等与权限已实现，同步 |
| add-user-management-auth-and-migrations | 身份、会话、权限与迁移已实现；协调默认HTTPS及显式临时HTTP例外后同步 |
| serve-web-dist-from-fastapi | 前端托管、SPA回退和API资源边界已实现，同步 |
| document-and-publish-project | 文档与历史发布任务完成；补齐Purpose和当前项目状态说明后同步 |
| register-selflore-start-tab | 实际API/Web服务和组合配置匹配，核对后同步 |
| enable-registration-by-default | 默认注册和显式关闭回归通过，同步 |
| add-guest-demo-workspace | 只读游客空间与隔离回归通过；修正认证检测/业务请求措辞后同步 |
| build-card-knowledge-workspace | 四页业务及最后的移动底栏中央新建完成44/44项，七项能力均已同步，后续按用户要求归档 |

本地部署已归档：setup-ssh-cicd-deployment、automate-local-windows-deployment、stage-database-migrations-before-deploy、keep-local-deployment-out-of-git、separate-local-deployment-openspec。

旧“忽略整个OpenSpec”策略作为历史附件保留，并声明skip_specs，不参与当前规格同步。自动发布规格已与实际四种互斥模式、携带迁移的发布包和显式迁移阶段协调。本地部署归档仍在Git忽略范围内。

三个原本未勾选的旧UI变更，其任务按用户决定明确记为取消并关闭，未将旧视觉要求标为当前实现。所有归档目录都保留archive-review.md供逐项追溯。

## 验证与边界

- 本轮前端23项测试通过，lint和TypeScript/Vite构建通过。
- 后端离线36项通过；31项数据库测试未运行，skip不视为通过。已核对此前61项完整隔离验收、4项浏览器验收、迁移演练及实际开发库备份迁移记录。
- 首轮后端测试的临时父目录缺失已补齐，复跑无错误。
- PowerShell/Bash部署脚本语法与临时替身迁移闸门测试通过；未连接服务器。
- 同步22项有效能力delta，主项目与本地部署分别严格校验。
- 归档移动逐文件SHA-256一致；应用源码、迁移文件、部署脚本、既有Git初始化归档及Git索引均保持不变。仅OpenSpec工件、本地部署说明和PROJECT_OVERVIEW中的规格状态做了修订；未Git提交、推送或生产发布。
