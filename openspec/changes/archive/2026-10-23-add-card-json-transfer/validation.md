# 验收记录

- 变更：add-card-json-transfer；日期：2026-10-23（Asia/Shanghai）。
- 工作区：`C:\Users\wangz\.codex\worktrees\card-json-transfer\selflore`；分支：`codex/card-json-transfer`。
- 基线提交：`4a0d606a7eabf76589b3e36fffbdcf512c848ab7`。实现及规划为未提交工作区修改；新文件使用intent-to-add以便审阅完整diff，没有创建提交、发布或归档。原G:\selflore工作区修改未复制、未改动。
- 仅使用新建的一次性6179／6180测试实例及独立测试媒体目录；未迁移日常6171库或生产库。所属测试集群均已停止，当前未保留24568／24569监听。

## 自动验证

| 检查 | 结果与证据 |
| --- | --- |
| API完整回归 | `uv run --frozen --no-env-file python ../../scripts/ci_backend.py`，235 passed，0 failed，0 skipped；2项既有Starlette/httpx弃用警告 |
| API完整报告 | `.cache/ci-reports/backend-661b50b0d2ad49daa32bce903874d9b2.json`及同名XML，确认owned_clusters_stopped=true |
| 最后补强专项 | `tests/test_card_package.py`与`tests/test_card_transfer.py`，31 passed；补充管理员仅导出本人空集合、新复习状态与语义往返比较后复测通过 |
| 前端组件 | `pnpm test`，10个文件、82项通过，包括3项导入导出组件测试 |
| 前端静态与构建 | `pnpm format:check`、`pnpm lint`、`pnpm build`通过 |
| 真实接口浏览器 | `SELFLORE_TEST_ISOLATED=1 pnpm exec playwright test e2e/card-transfer.spec.ts`，1项通过；三种宽度JSON预检、导入、完整下载，6／12／18张统计正确，ZIP再次导入18张成功 |
| 独立布局浏览器 | 24569预览，`pnpm exec playwright test e2e/card-transfer-layout.spec.ts`，1项通过；API替身仅用于可控反馈与布局，不替代真实接口验证 |
| 公开文档 | `python scripts/check_docs.py`：118个本地链接，0错误；`python -m unittest discover -s scripts/tests -q`：17项通过 |
| OpenSpec及差异 | 严格校验通过，`git diff --check`无空白错误；Git仅提示既有Windows换行转换 |

后端验证覆盖六种卡片形式、全生命周期、正文与答案、隐藏清单列、完成时间、统一标签、前向／循环引用、手工链接及历史非知识条目关系；同账号与跨账号JSON／ZIP往返比较全部语义字段和引用拓扑，图片摘要保持。覆盖同批次并发重试／载荷冲突、预检无写入、事务故障回滚、发布部分原图后的磁盘失败和同批次恢复、损坏图片、恶意ZIP成员、正文转换后超限、2001张卡拒绝及超过一页完整导出。媒体故障恢复通过注入异常模拟中断遗留状态，未实际强杀生产进程。

## 截图生成与实际查看

浏览器为本机Chrome 155.0.8059.82。页面为`/me`，没有新增弹窗或共享主题改动。布局使用合成账号与长文件名／长错误路径；真实接口使用独立注册账号及仓库示例。

- 布局截图目录：`.cache/frontend-visual-review/card-json-transfer-layout/`；最终默认视口320×844、390×844、1280×900。
- 真实接口截图与下载目录：`.cache/frontend-visual-review/card-json-transfer/`；补充视口320×900、390×900、1280×900。
- 共生成49张PNG。用于本次验收的18张均已通过图像工具实际打开查看；其余31张为附加生成图，不作为视觉通过证据，不将仅生成等同于已审查。
- 逐文件查看标记、SHA-256和采用情况见`.cache/frontend-visual-review/card-json-transfer-review.json`，其中is_used_for_acceptance=true的18项即下表。

| 路由／状态 | 视口 | 实际查看文件（相对上述目录） | 已生成／实际查看 | 视觉结论 |
| --- | --- | --- | --- | --- |
| /me长路径错误、预检、处理中、成功、导出失败 | 320×844 | 布局目录`320-{error,preview,pending,success,export-error}-viewport.png`五张 | 是／是 | 已审查范围内未发现问题 |
| /me长路径错误、预检、处理中、成功、导出失败 | 390×844 | 布局目录`390-{error,preview,pending,success,export-error}-viewport.png`五张 | 是／是 | 已审查范围内未发现问题 |
| /me桌面长路径错误 | 1280×900 | 布局目录`1280-error.png` | 是／是 | 已审查范围内未发现问题 |
| /me真实接口初始与导出 | 320×900、390×900、1280×900 | 真实目录三种宽度的`{width}-initial.png`和`{width}-exported.png`六张 | 是／是 | 已审查范围内未发现问题；手机局部元素图的底栏遮挡以滚动视口图补充确认 |
| /me真实ZIP再次导入及页面整体 | 1280×900 | 真实目录`1280-page-bottom.png` | 是／是 | 已审查范围内未发现问题 |

构建证据：Profile-DXFI91El.js SHA-256 `a8eb8b67630b04b643e124e03a2ba1ddfc2984eb6c6de79324bb5a24e2a26815`；Profile-BP8ZwnGa.css SHA-256 `9c425c5e1dcfa80548c6f7c3a7a4c3de28463c73aa54c42d817383c208982fea`。该构建及截图为首轮验收记录；后续文件按钮修正见本文末尾，新证据替代此处受影响展示结论。

## 问题与复测

- 首轮集成测试发现回收站导入需写trashed_at，已补齐并通过全生命周期往返；Windows fsync句柄与长媒体路径问题已修复，原图与共享图片往返、磁盘失败恢复复测通过。
- 新增0009迁移后同步既有升级测试链，并将故障迁移的测试编号移至0010；完整升级、授权及回滚回归通过。
- 完成时间初始断言将时区显示形式误当差异，改为比较同一时间点；语义往返测试同时核对其他字段。
- 测试端口被另一发布验证流程使用期间，只读确认并等待其释放，未复用或停止其进程。
- 手机元素截图会把固定底栏拍入局部区域，不能据此判断末尾不可达。补拍滚动后的844高度视口并实际查看，长字段换行、错误、状态和按钮均可读可达。浏览器实际滚动到页末，并使用焦点和Enter确认导入；未发现需要修改展示源码的问题。

## 交付与未覆盖范围

- 规范、六种形式示例、Schema位于`docs/card-transfer/`；API携带副本并有一致性测试，维护者可在apps/api运行`uv run python -m app.card_transfer_docs`同步。`.gitignore`仅新增该文档子目录例外。
- 新迁移0009需随正式部署单独执行；本次没有真实业务库迁移。新增表可保留供旧应用回退，不删除导入卡片或ready原图。
- 内容包不含合集结构、账号资料、复习历史／调度、活动日志或未关联图片；2000张／32 MiB JSON／512 MiB ZIP限制已文档化，超限明确失败，不截断成功包。
- 视觉验收仅覆盖个人页新增操作及相关状态；未宣称全站视觉通过。未检查真实手机软键盘／安全区、其他浏览器、额外断点和屏幕阅读器。真实浏览器往返为无图示例；含图片的ZIP语义与原图往返由真实数据库／媒体API集成测试覆盖，布局里的1张图片计数为替身数据。
- 49张图中未列为采用的31张不作验收结论。未进行生产部署、生产故障演练或实际强杀进程测试。


## 文件选择按钮视觉修正（2026-10-23）

用户指出原生“选择文件”按钮与页面不一致，首轮视觉审查漏掉了这一点。本轮仅修改CardTransfer.css的局部文件按钮样式，复用既有按钮的字体、配色、细边框、2px圆角和悬停效果，并保留原生输入、可见焦点、44px点击高度与禁用状态。没有修改业务接口或导入流程。

- 自动检查：重新构建通过；3项card-transfer组件测试通过；lint、format:check通过。未重复运行无影响的后端全套测试。
- 浏览器：Chrome 155.0.8059.82，24569独立API替身预览；320×844、390×844、1280×900。现有布局用例通过，逐宽度实际使用Space打开文件选择器并取消，继续验证选文件、预检、处理中禁用、结果与页面末尾可达。
- 新截图位于`.cache/frontend-visual-review/file-selector-style/`，与首轮截图分开保存。采用并实际打开查看9张：`320-file-focus.png`、三种宽度的`{width}-file-hover.png`、`320-pending-viewport.png`、`390-pending-viewport.png`、`1280-pending.png`、`320-error-viewport.png`、`390-error-viewport.png`。逐文件摘要见同目录review.json；其他自动生成图不作为已查看的证据。
- 视觉结论：已审查范围内未发现文字裁切、控件错位或操作受阻；选择文件按钮不再保留浏览器默认灰色立体外观，焦点和禁用状态可辨。长错误路径正常换行。新图替代首轮涉及文件选择控件的展示证据；未修改全局上传控件。
- 范围限制：本轮只用Chrome验证此局部样式，未补测其他浏览器、真实手机系统文件选择器或全站共享样式。工作区仍为原分支未提交修改；没有发布、归档或迁移业务库。

本轮构建：`Profile-CBL1h3yF.css` SHA-256 `e200d254f6910957233b512f03ce173e20bdde4fb5b3fc79e6fb3312c7d9a9c4`。


## 精简导入导出页面（2026-10-23）

- 用户要求减少介绍和小字。移除默认显示的两段范围／限制介绍、三项文档链接和重复导入说明，将它们合并到默认折叠的“格式与说明”；保留简短归档／回收站提示。预检数量和新增语义合并显示，不再额外显示重复的预检成功说明。未使用更小字号压缩内容。
- 更新当前change设计、需求及任务，说明可通过键盘展开；既有接口、文件按钮样式及导入流程不变。
- 自动检查：pnpm build、pnpm lint、pnpm format:check通过；3项card-transfer组件测试通过（包括默认折叠／展开）；独立API替身浏览器布局测试通过，三种宽度均实际用Enter展开说明、Space打开文件选择器，再完成预检、确认、状态和滚动流程。本轮没有后端变化，不重复数据库回归。
- 真实浏览器：Chrome 155.0.8059.82，视口320×844、390×844、1280×900。截图独立保存在`.cache/frontend-visual-review/compact-transfer/`，首轮及文件按钮修正截图保留为历史，不再代表当前文案。
- 实际打开查看并采用8张：三种宽度的`{width}-compact-viewport.png`，`320-help-viewport.png`、`390-help-viewport.png`、`320-preview-viewport.png`、`1280-preview.png`、`1280-help.png`。逐文件摘要见同目录review.json；其余自动生成图不作已查看的证据。
- 视觉结论：已审查范围内未发现问题。默认区域只显示操作及必要提示；手机展开内容正常换行，说明末尾可滚动到达且未被底栏遮住；预检数量和确认按钮可读，展开焦点可见。未发现需要再次修复的阅读或操作问题。
- 范围限制：本轮检查个人页该区域的折叠、展开及代表状态，API为测试替身；没有重做真实数据库往返或其他浏览器／真实手机检查，没有修改全局样式。仍在codex/card-json-transfer未提交工作区，无发布或归档。

本轮构建：`Profile-DY7pkz5J.css` SHA-256 `f6b1114b9c597af3a19149b388f04848849aefa821edd2fd5e8e3381f53ee38e`。

本轮构建：`Profile-jAUHbJwb.js` SHA-256 `8c399db01e32e37f26c5f434f79dbcecd448fee728c27c6c1bfc7e785ee9609d`。


## 归档与分支提交（2026-10-23）

用户明确授权同步7项新规范、归档并提交本分支。17项任务全部完成，新增card-json-transfer主规格已逐字核对7项要求及全部场景，30项主规格严格校验通过。归档目录为openspec/changes/archive/2026-10-23-add-card-json-transfer，保留原有规划、delta、验证记录和.openspec.yaml。

截图、报告与归档前完整补丁另存于G:\selflore\.cache\card-json-transfer-handoff-20261023，manifest.json记录文件摘要，便于后续回收worktree时保全证据；历史截图绝对路径仍指向原worktree，相同相对路径可在该保全目录找到。此阶段只提交codex/card-json-transfer，不合入主线、不推送、不部署、不迁移实际业务库、不回收worktree。归档与规范同步没有修改业务源码，不重新运行此前已通过的业务测试；提交前复核文档和差异检查。
