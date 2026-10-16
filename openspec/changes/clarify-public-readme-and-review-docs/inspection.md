# GitHub 阅读体验与目录审查

审查日期：2026-10-16。仓库根：`G:/selflore`；基线提交 `90ede04`。本次更新根 README，其余问题仅审查，没有搬移、删除或重构。

## 判断

应用本身的前后端边界清楚，`apps/web` 与 `apps/api` 的结构适合当前规模。对 GitHub 首次访客而言，原有说明不足：根 README 只有7行，介绍早于资料卡与备忘；后续说明又混有旧状态和本机验收记录。主要问题是信息来源重复、当前状态失真、代码命名滞后和格式压缩，不是目录层级必须重建。

本次已把根 README 改为产品入口，补充真实演示链接、当前功能、运行前提、相对路径启动、目录及公开文档导航。HTTPS 页面、API 版本和前端版本均只读核验成功。

## 依据与优先级

| 优先级 | 发现 | 依据 | 建议 |
| --- | --- | --- | --- |
| 高 | 根 README 缺演示、资料、备忘和启动路径，迁移枚举过时 | 修改前 README 第3–7行；当前 `App.tsx:70` 四导航及 migrations/0001–0006 | 本次已修复；后续继续保持入口级说明，不重复迁移版本明细 |
| 高 | 前端子 README 完全是脚手架模板，读者看不到项目入口与命令 | `apps/web/README.md:1`、`:3` | 替换为前端启动／测试命令、目录职责和后端依赖；删除模板插件推介 |
| 高 | 当前概览写旧导航，维护卡仍写未发布，且验收数字来自不同阶段 | `PROJECT_OVERVIEW.md:3`、`:14`；`MAINTENANCE.md:5`、`:70`、`:81` | 合并产品概览至 README；维护卡只保留日常操作，历史状态移入带日期的变更记录 |
| 高 | 数据库说明顶部仍写迁移链只到0003；卡片迁移页先说新增两版，再拼入0006、0005 | `apps/api/DATABASE_SETUP.md:44`；`apps/api/CARD_MIGRATIONS.md:3`、`:14` | 首次初始化页只说明执行完整链，迁移页按版本排序并区分历史实例与通用命令 |
| 中 | API 说明重复“资料卡与附件”标题，前一个为空；媒体维护页保留未标明历史时间的“尚未生产演练”结论 | `apps/api/WORKSPACE_API.md` 中备忘章节前后的同名标题；`MEDIA_STORAGE.md` 的 Linux 发布准备段 | 去掉空重复标题，运行手册写当前操作和边界，旧验收结论转入带日期的记录 |
| 中 | 固定 Windows 本机路径和6171端口，与通用5432示例混用，初次运行需要跨文件拼接 | `LOCAL_START.md`、`MAINTENANCE.md`、`apps/api/DATABASE_SETUP.md` | 公共说明用仓库根相对路径；先区分固定 Windows 启动与通用手动配置。根 README 已明确此区别 |
| 中 | 测试说明把仅本机部署工具写在公开验证段落中 | `apps/api/WORKSPACE_TESTING.md:102`；`.gitignore:7` | 分开“克隆可复跑的测试”和“维护者本机发布门禁”，后者不应成为公共开发前提 |
| 中 | 统一卡片页仍叫 Knowledge，独立 Opinions 页还保留在生产源码目录 | `apps/web/src/App.tsx:11`、`:72`；`features/knowledge/Knowledge.tsx`；`workspace.test.tsx:10` | 后续将统一列表重命名为 `features/cards/Cards.tsx`；核对旧 Opinions 页用途并迁移对应测试。当前仅测试静态导入旧页，不能据此直接删除 |
| 中 | JSX 单行过长，代码行数少但审阅困难 | `Knowledge.tsx:32` 为1679字符；`App.tsx:72` 为1350字符；`Editor.tsx:57` 为990字符 | 先统一格式，再按职责拆组件；不要把单行压缩误认为实现简洁 |
| 中 | 后端 workspace 路由覆盖多类业务，repositories 名称比实际职责宽 | `app/routers/workspace.py` 的卡片、备忘、分类、合集、复习、个人接口；`repositories/workspace.py` 为 SQL 辅助函数，业务 SQL 位于 services | 后续按 cards／memos／collections／reviews／profile 拆路由；明确 repositories 是数据访问辅助层，不必为目录形式引入 ORM |
| 低 | 当前 Git 跟踪清单中没有 CI workflow、许可证或贡献入口 | `git ls-files`，不是仅查看本机空目录 | 对外协作前选择是否提供 LICENSE 和简短 CONTRIBUTING；接入适合公开环境的检查。未指定许可，本次不代选 |
| 低 | GitHub 产品展示缺截图 | README 未引用截图；现有设计截图在忽略目录 | 挑选已脱敏的桌面与移动截图，放入单独受跟踪的公共资源目录，避免直接公开整个 docs |

## 文档冗余应怎样收敛

当前受跟踪的14份非 OpenSpec Markdown 文档包含工程约定，不代表14份都多余。数据库、认证、API、媒体和测试面对不同任务，拆开合理；重复主要来自下面几组职责交叉：

| 重复主题 | 现有位置 | 建议单一来源 |
| --- | --- | --- |
| 产品定位、功能和技术栈 | README、PROJECT_OVERVIEW、MAINTENANCE、API README | README 负责产品；架构复杂后再单列架构页。PROJECT_OVERVIEW 可合并后移除，先修正入链 |
| 一键启动、手动启动、端口、密码配置 | MAINTENANCE、LOCAL_START、API README、AUTH_CONFIGURATION | LOCAL_START 负责固定入口；AUTH_CONFIGURATION 负责通用环境变量和手动运行；其余只链接 |
| 首次建库与迁移 | DATABASE_SETUP、CARD_MIGRATIONS、MAINTENANCE | DATABASE_SETUP 负责首次准备；CARD_MIGRATIONS 负责升级机制和账本；维护卡只列入口 |
| 功能版本说明 | MAINTENANCE 中按日期追加的备忘／资料段、PROJECT_OVERVIEW | 当前功能放 README；操作约束放专项页；完成时的验收叙述留对应 OpenSpec validation |
| 测试数量、历史“未部署”等状态 | 维护卡、启动说明、迁移说明及历史变更 | 历史结果只放带日期／提交的验收记录；常用文档只保留如何验证 |
| 图片与备份操作 | MEDIA_STORAGE、DATABASE_BACKUP、MAINTENANCE | 媒体页负责配置／监控；备份页负责备份／恢复；维护卡只提供链接 |

`openspec/specs` 是当前行为约定，`openspec/changes/archive` 是设计与验收历史。它们不应因“相同功能在两处出现”而被简单删除；但也不应要求新用户先读提案才能启动应用。

## 目录是否需要重组

### 当前可保留

- `apps/web`、`apps/api` 两个应用目录有各自依赖清单和锁文件，边界明确；没有必要为了展示增加一层 packages 或 workspace 配置。
- 前端按 features、components、lib 分工，后端按 routers、schemas、services 分层，SQL 迁移和测试独立，整体可理解。
- `start-local.cmd` 等根入口是轻量包装，脚本实现在 `scripts/`，便于 Windows 用户运行，不属于无意义重复。
- 本机 `.cache`、`.pnpm-store`、backups、deploy、local-deployment、docs 均不在 Git 跟踪清单中，GitHub 不会展示这些本机运行目录。不能把本机根目录的全部文件夹当成公开仓库杂乱证据。

### 建议的后续公共文档布局

下列为建议，尚未实施：

```text
README.md                 产品、演示、最短启动与文档入口
CONTRIBUTING.md            开发及提交流程（如开放协作）
MAINTENANCE.md             简短维护入口
docs/public/
  local-development.md    新环境准备与本地运行
  database.md             建库、角色及增量迁移
  authentication.md       认证与运行配置
  testing.md              自动测试与视觉审查
  media-storage.md        图片存储、诊断及容量指标
  backup-recovery.md      备份与恢复
  api.md                  接口约定
apps/web/README.md         前端专用命令及目录入口
apps/api/README.md         后端专用命令及目录入口
openspec/                 规格与历史变更
```

目前 `.gitignore` 整体忽略 docs。若采用此布局，必须先精确放行 docs/public，继续隔离私有设计／验收材料，再更新所有入链；不能直接取消 docs 的整条忽略规则。目录移动的收益低于修正文档内容，建议后置。

## 分阶段执行建议

1. 先修正文档内容：替换前端模板 README、删除维护卡中的过期当前结论、同步迁移说明、合并重复概览。无需搬文件即可明显改善。
2. 再做协作入口：选择许可证、补贡献说明、增加脱敏截图；根据公开协作需要设计 CI。是否开放复用和贡献需由维护者决定。
3. 最后整理代码：统一格式，统一卡片页命名，处理旧 Opinions 页和测试，再拆 workspace 路由。分为独立代码变更并执行相应测试与视觉验收。

## 核验范围与限制

- 已检查 Git 跟踪清单、忽略边界、14份公开 Markdown、前后端入口与关键分层、依赖及锁文件存在性。公共 Markdown 的47个本地文件链接均指向被跟踪文件，没有把“内容过期”误报成“链接失效”。
- 主要运行依赖为 React／Vite、FastAPI／psycopg、PostgreSQL；在已检查依赖及业务入口中未发现直接 LLM 服务调用，不需要将 AI 服务列为运行前提。这不是全仓依赖安全或秘密扫描。
- 原生 GitHub 页面未发布／预览，未执行首次克隆安装、构建、业务测试或数据库写入。没有把上一轮测试结果当成本次验证。
- 本次未修改除根 README 之外的产品说明文件，以上剩余问题仍存在；未更改源代码或现有未提交 CSS。
