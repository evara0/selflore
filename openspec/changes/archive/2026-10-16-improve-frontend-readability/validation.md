# 前端可读性整理验收

日期：2026-10-16。基线提交`36d2e393c8d0e77dba05e35e90acd910ea1fa1bd`，开始时工作区干净。当前结果为该提交之上的未提交工作区；没有归档、推送或部署。

## 结果与边界

- 固定Prettier3.9.10开发依赖，增加`pnpm format`／`pnpm format:check`及CI检查。src下TS／TSX和前端根TS配置采用统一格式；限定`.gitattributes`确保Windows也以LF检出。运行依赖未变，锁文件仅新增该格式化工具。
- 统一列表迁至`features/cards/Cards.tsx`，旧Knowledge及Opinions页面源码删除；Review仍保留在knowledge。旧观点用例迁到实际Cards页面，保留URL选中、反向链接及无学习操作断言；增加3项旧URL目的地及查询参数兼容测试。
- App只保留身份及认证控制，框架／导航、路由及兼容入口、受控认证弹窗分别位于WorkspaceLayout、WorkspaceRoutes、AuthDialog。Editor为29行的类型分派入口；卡片状态与提交、组织来源区、合集编辑器分别位于CardForm、CardSources、CollectionEditor。未改DOM、CSS、文案、保护规则、提交payload及状态key。
- 前端说明、贡献指南和测试手册已同步结构、格式和替身回归入口。没有旧页面的生产源码导入。后端、迁移和两个CSS文件相对基线均无变化。

## 自动检查

| 检查 | 结果 |
| --- | --- |
| pnpm10.33.0冻结安装 | 通过，锁文件一致 |
| Prettier格式检查、Oxlint | 通过，无新增Lint告警 |
| 完整Vitest | 70项通过，7个测试文件 |
| TypeScript／Vite构建 | 通过 |
| Chrome行为回归`e2e/editor-boundaries.spec.ts` | 3项通过：注册登录退出；资料来源7字段及503重试的请求身份；合集创建及封面保存 |
| 当前公开Markdown | 106个本地链接通过 |
| actionlint1.7.12 | CI新增格式步骤检查通过；未配置shellcheck |
| OpenSpec严格校验、Git diff空白检查 | 通过 |

机械格式阶段单独核对34个文件的运行AST；忽略括号及等价的相邻JSX文字拆分后完全一致，记录位于`.cache/frontend-readability/format-comparison.json`。此结论仅适用于格式阶段，不将职责重构也声称为完全相同AST。既有effect规则豁免改为仅包围原effect的注释区间，避免展开换行后原来的next-line失效。

新增兼容测试初次误嵌在另一测试内部，已移到顶层并复测。账户测试起始URL显式设置`type=all`，避免列表默认筛选初始化抢占账户导航；旧URL另外验证，没有删除权限或CSRF断言。浏览器替身初次遗漏登录图片读取、空请求体及多status定位，已补齐后3项通过；测试写入只在内存，无数据库或业务服务。

## 截图生成、查看与视觉结论

Chrome155.0.8059.40，Windows，新上下文，设备缩放比1，中文及Asia/Shanghai。基线及最终构建由自有127.0.0.1:24569预览。四主页、资料详情及认证使用原生游客示例；卡片及合集编辑使用合成登录身份与GET替身。没有使用真实账号、笔记、用户图片或既有浏览器会话。

先等待标题、数据、字体及图片就绪，再截图。baseline和after各24张；下表after的每张图片均实际使用图像查看工具打开。末次仅拆开卡片／备忘查询参数表达式，构建后重做全部截图，并复看卡片、备忘及认证背景的9张；其余15张最终图像字节与已查看内容相同。

| 页面／状态 | 320×844 | 390×844 | 1280×900 | 实际查看／结论 |
| --- | --- | --- | --- | --- |
| 卡片／游客 | [图](../../../../.cache/frontend-readability/after/cards-320.png) | [图](../../../../.cache/frontend-readability/after/cards-390.png) | [图](../../../../.cache/frontend-readability/after/cards-1280.png) | 是，分类及筛选与基线一致 |
| 备忘／游客 | [图](../../../../.cache/frontend-readability/after/memos-320.png) | [图](../../../../.cache/frontend-readability/after/memos-390.png) | [图](../../../../.cache/frontend-readability/after/memos-1280.png) | 是，清单框线、标题和导航未改变 |
| 合集／游客 | [图](../../../../.cache/frontend-readability/after/collections-320.png) | [图](../../../../.cache/frontend-readability/after/collections-390.png) | [图](../../../../.cache/frontend-readability/after/collections-1280.png) | 是，封面与入口未改变 |
| 我的／游客 | [图](../../../../.cache/frontend-readability/after/profile-320.png) | [图](../../../../.cache/frontend-readability/after/profile-390.png) | [图](../../../../.cache/frontend-readability/after/profile-1280.png) | 是，资料及统计层级未改变 |
| 资料详情／游客 | [图](../../../../.cache/frontend-readability/after/detail-320.png) | [图](../../../../.cache/frontend-readability/after/detail-390.png) | [图](../../../../.cache/frontend-readability/after/detail-1280.png) | 是，材料、原色图片及框线未改变 |
| 资料新建／合成登录 | [图](../../../../.cache/frontend-readability/after/editor-320.png) | [图](../../../../.cache/frontend-readability/after/editor-390.png) | [图](../../../../.cache/frontend-readability/after/editor-1280.png) | 是，分派／表单／来源拆分无可见变化 |
| 合集新建／合成登录 | [图](../../../../.cache/frontend-readability/after/collection-editor-320.png) | [图](../../../../.cache/frontend-readability/after/collection-editor-390.png) | [图](../../../../.cache/frontend-readability/after/collection-editor-1280.png) | 是，输入、选择器及保存按钮未改变 |
| 登录弹窗／游客 | [图](../../../../.cache/frontend-readability/after/auth-320.png) | [图](../../../../.cache/frontend-readability/after/auth-390.png) | [图](../../../../.cache/frontend-readability/after/auth-1280.png) | 是，弹窗位置、文字及控件未改变 |

最终24组PNG字节、body序列化DOM均与基线完全一致，均无页面级横向溢出；记录见`.cache/frontend-readability/comparison.json`及after/report.json。CSS构建摘要仍为`571cb8e6a17553a4d3f64fc5b19326e508ef38b85c7b50ab3df06cb1f9c09c1f`。图像一致与DOM一致是额外依据，实际截图查看另行完成，二者没有互相替代。

所有场景实际滚动至末尾；桌面页脚、代表末尾控件可滚动到视口，移动页脚按既有CSS隐藏。执行Tab键及弹窗关闭；实际注册、登录、退出、失败重试和保存由3项Chrome测试另行验证。

| 问题／发现 | 处理及复测 |
| --- | --- |
| 首次after截图与重建并行，构建清空dist期间出现动态模块读取失败 | 属验证调度错误；改为构建结束后串行截图，最终24组均无页面异常 |
| 桌面较长分类名称按现有侧栏宽度换行 | 基线与最终一致，一般排版现状，本次保留；不将可读性整理扩大为样式修改 |

结论：已审查范围内未发现本次重构引入的展示变化或阅读／操作回归。未覆盖真实移动设备键盘、安全区、其他浏览器、所有数据长度组合、实际上传及真实后端闭环；未进行新的对比度数值测量，不作全站视觉或业务保证。未修改公开README截图，因为界面图像保持一致。

## 交付状态

任务7/7完成，本机验证通过。2026-10-16按用户后续明确指令归档，并进入提交、推送、远端CI和生产发布流程。本记录中的测试与截图为发布前验证；CI及实际部署结果以对应提交的GitHub Actions和发布执行器报告为准。
