# 实施与验收记录

- 日期：2026-10-22（Asia/Shanghai）；审查者：Codex。
- worktree：`C:\Users\wangz\.codex\worktrees\788d\selflore`；分支：`codex/add-tabular-checklists`。
- 创建时HEAD为20d52e5，干净工作区在独立功能分支安全快进至2554df180e86ba2438d5012422a7c4c928f0dab7。统一标签和快速收录基线保留。
- 当前为该基线上的未提交修改；未提交、推送、部署、合并或归档。未在main或9ec6 worktree实施，未编辑G:\selflore的用户文件。

## 实现与兼容

- `0008_tabular_checklists.sql`仅增量添加列名、显示数与两个附加文本槽位；未修改0001–0007。首列继续映射text，行ID、顺序、完成时间及关系保留；隐藏列保值，旧PATCH按稳定ID保留省略的附加值。
- schema/readiness与能力标记升级为`reference-memo-tags-table-v1`；整库备份已包括新字段，无新独立数据文件。旧应用不作为多字段清单直接写入回滚目标。私有发布工具未修改、未发布或验证。
- `cards.py`和`memos.py`负责兼容合并、全部字段搜索、事项返回元数据、新增关联仅knowledge；原有异类关联按同一行保留。
- `EditorFrame.tsx`提供共享框架和类型入口；MemoEditor复用CardSources，CardForm提供固定knowledge的内嵌模式。父表单保持挂载，创建、取消后恢复当前行焦点；独立知识保存状态明确展示，重试使用既有幂等ID。清单勾选不修改复习调度。
- MemoContent供详情与合集阅读共用；未完成事项显示字段名和值。桌面对齐列，手机逐行字段。

## 自动验证

| 检查 | 结果与范围 |
| --- | --- |
| OpenSpec | `openspec validate add-tabular-checklists --strict`通过 |
| 格式／lint／类型／构建 | Prettier、Oxlint、`tsc -b`、Vite最终构建通过 |
| 全部Vitest | 原生环境一次完整运行9文件79项通过；焦点／展示修正后只补测App、memo、unified-tags共29项，通过 |
| 全部后端pytest | 一次完整隔离运行204项：201通过，3项旧迁移断言失败，0 skip。新增0008与测试故障版本号冲突、旧SELECT *比较含新列；调整测试断言后仅复测这3项，全部通过。业务实现未因这些失败修改 |
| 后端报告 | `.cache/ci-reports/backend-fe28c3d9ae974cea94b1f3a36decc905.{xml,json}`（全量）；`backend-aaeedf32845545a88628e64c7dcb9be8.{xml,json}`（3项定向） |
| 浏览器 | `tabular-checklists.spec.ts`、`memo.spec.ts`、`editor-boundaries.spec.ts`共12项通过；`memo-layout.spec.ts`仅320／390／1280三项通过；统一标签仅四类编辑器保存功能项通过，未跑旧大规模视觉矩阵 |
| 文档／diff | `scripts/check_docs.py`检查115个本地链接，0错误；`git diff --check`通过 |

后端使用任务拥有的6179、6180一次性PG18集群，完整CI脚本均停止所属集群。没有连接6171或生产。第一次沙盒运行出现uv缓存权限、Vitest worker超时和initdb超时，未计为通过；改用锁定uv环境中的解释器与正常原生执行后完成上述验证。后端两个第三方弃用警告未影响断言。

### 针对性闭环

旧单列迁移、SQL约束、三列保存／重载、隐藏后旧PATCH保值、恢复列、附加字段搜索、统一标签、勾选时间、排序与合集字段均通过真实接口验证。旧资料关系通过前版本合法数据种子保留；新增资料关系拒绝。

浏览器真实创建合成的crontab -l／systemctl list-timers／schtasks清单：选择已有knowledge、空表单取消返回原行、问答创建、非法填空拒绝后修正、创建响应丢失后同client_request_id重试且知识仅增加一张、父清单保存失败后保留关联再重试、详情跳转、键盘排序、完成状态与标签重载均通过。

### 备份恢复

任务浏览器库的确切目录为`.cache/card-tests/browser-b2c2951a/pgdata`，只读核对后执行pg_dump并恢复至同一隔离集群随机新库。最终按项目原owner／恢复role操作，数据及结构签名一致，指定稳定ID的三条多字段行恢复正确；恢复库已移除。证据：`.cache/card-tests/tabular-backup/result.json`、`signatures.json`和`synthetic.dump`。早期辅助脚本以postgres归属恢复扩展导致签名不同，随后修正为既有恢复role；新列本身未发现差异。最后断言按清单ID避免两轮合成样例同名混淆。

## 视觉审查

真实Chrome 155.0.8059.82，当前构建、合成数据和本地24568隔离API。默认视口320×844、390×844、1280×900。最终入口产物`index-CmiVIRuj.js`、`index-R5fn2dgl.css`；源码／构建／截图哈希记录在截图目录的`manifest.json`。

下表每张截图均已生成，并由图像查看工具实际打开；共19张。截图相对根目录：`.cache/frontend-visual-review/tabular-checklists/`。长全页图用于结构，行字段、行操作、知识重试、保存区补充原尺寸局部／视口图。固定导航会在浏览器全页截图中保留在捕获时的视口位置，不能据此推断页面不可滚动；另外实际滚动和坐标检查验证操作可达。

| 路由／状态 | 视口 | 截图文件 | 已生成 | 已实际查看 | 视觉结论 |
| --- | --- | --- | --- | --- | --- |
| /new?kind=memo&memo_format=checklist 三列草稿 | 320 | checklist-editor-320.png | 是 | 是 | 行卡片，字段名与值保留 |
| 同上 | 390 | checklist-editor-390.png | 是 | 是 | 同上 |
| 同上 | 1280 | checklist-editor-1280.png | 是 | 是 | 列对齐，来源侧栏与正文分区清楚 |
| 编辑首行字段局部 | 320 | editor-row-320.png | 是 | 是 | 首字段输入完整可读 |
| 编辑首行局部 | 1280 | editor-row-1280.png | 是 | 是 | 勾选与文字横向对齐、三列可读 |
| 行操作键盘焦点 | 320 | editor-actions-viewport-320.png | 是 | 是 | 新建知识、关联与排序可滚动到导航上方 |
| 保存区视口 | 390 | editor-save-viewport-390.png | 是 | 是 | 独立保存提示、取消／保存可达 |
| 清单保存失败 | 390 | checklist-save-error-390.png | 是 | 是 | 草稿、知识状态和错误保留 |
| 行内知识响应丢失／重试 | 390 | knowledge-retry-390.png | 是 | 是 | 问答、固定类型和来源结构清楚 |
| 同上错误与保存视口 | 390 | knowledge-retry-viewport-390.png | 是 | 是 | 错误文字、取消和重试按钮可读 |
| /memos/:id 三列详情 | 320 | checklist-detail-320.png | 是 | 是 | 字段名、值、链接与完成状态可辨 |
| 同上 | 390 | checklist-detail-390.png | 是 | 是 | 同上 |
| 同上 | 1280 | checklist-detail-1280.png | 是 | 是 | 表头与各列对齐 |
| /memos?view=open&q=systemd | 390 | open-items-390.png | 是 | 是 | 附加值命中搜索，所属清单与知识入口可读 |
| /collections/:id?view=read | 1280 | collection-reader-1280.png | 是 | 是 | 共用三列表格阅读，禁用勾选清晰 |
| 普通备忘共享编辑器 | 390 | memo-shared-editor-390.png | 是 | 是 | 标题、正文、来源和类型入口一致 |
| 事实知识共享编辑器 | 320 | knowledge-shared-editor-320.png | 是 | 是 | 问答与窄屏类型入口可读 |
| 观点共享编辑器 | 1280 | opinion-shared-editor-1280.png | 是 | 是 | 正文与来源两栏结构正常 |
| 资料共享编辑器 | 390 | reference-shared-editor-390.png | 是 | 是 | 快速收录、摘录、图片区、来源保持 |

| 问题 | 影响／处理 | 复测 |
| --- | --- | --- |
| 最初详情截图抓到懒加载 | 截图证据不合格；等待实际标题和加载状态消失后重拍 | 详情三个宽度最终图片已查看 |
| 编辑勾选文字纵排 | 补明确flex-direction:row；创建知识自动聚焦标题 | 行局部、手机操作视口及相关29项组件回归通过 |
| 桌面完成表头挤为两行 | 改为完成状态✓标记 | 最终详情／合集截图已更新并查看 |
| 手机局部截图被固定导航切到 | 将字段局部限定至完整首字段，另拍行操作视口；事项截图纠正为真实390宽度 | 新局部和事项截图已打开 |

键盘Enter排序、返回原行焦点有浏览器断言；手机保存按钮与导航的坐标比较通过，实际滚动至来源末尾并执行Tab。标签触控选择由既有四编辑器功能用例覆盖。已审查范围内未发现未解决的阅读或操作问题；这是抽样结论，不是全站保证。

未覆盖：真机软键盘／安全区、Safari／Firefox、全部中间断点、200行三列的视觉压力、完整屏幕阅读器流程、所有历史状态×所有宽度，以及日常／生产迁移与私有发布工具。本次未重跑大规模旧视觉矩阵；旧布局用例另有自动生成截图，不作为本次人工视觉结论证据。

## 收尾状态

OpenSpec apply状态为all_done，8/8任务完成，change仍在changes下未归档。浏览器环境启动器已返回`Owned browser server and database stopped.`；所属API和数据库均已停止，合成缓存／截图留存。最终工作区保留源码、迁移、测试及文档修改，未暂存／提交。
