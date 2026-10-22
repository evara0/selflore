## Scope

2026-10-22在独立worktree实施。基线与当前HEAD均为 `20d52e53165d2df3759a3b9e2b9843a90b2ec0e5`；全部修改尚未提交。主仓库 `G:\selflore` 未写入，其用户未提交的 `.gitignore`、`MAINTENANCE.md` 保留。本worktree的维护卡按本次行为更新。没有归档、提交、推送或部署，没有连接日常6171或生产库。

## Automated Validation

| 范围 | 实际命令／证据 | 结果 |
| --- | --- | --- |
| 后端、隔离迁移、权限、备份恢复、规模查询 | `apps/api/.venv/Scripts/python.exe scripts/ci_backend.py --pg-bin <PG18 bin>`（项目根目录；PG18路径为 `D:\Program Files\PostgreSQL\pgsql\bin`） | 201 passed，0 failed，0 skipped；`.cache/ci-reports/backend-685a6d9ccb914caba5a54f99cf28d35d.json`及同名XML |
| 前端组件与URL | 在apps/web运行 `pnpm test` | 79 passed，9文件；最终顺序重跑通过 |
| 前端静态及构建 | 在apps/web运行 `pnpm lint`、`pnpm build`、`pnpm format:check` | 通过 |
| 统一标签真实Chrome功能 | `pnpm exec playwright test e2e/unified-tags.spec.ts`及混合URL补充用例 | 两项主用例和一项混合URL用例通过；包含四类型编辑／重载、设置管理、旧URL、混合客户端、键盘与触控 |
| 既有真实浏览器回归 | workspace、reference、memo、guest、editor-boundaries五个spec | 17 passed；覆盖复习评分、清单完成、合集顺序、图片、旧路由、登录隔离及快速收录 |
| 本机发布工具模拟 | `python deploy/tests/test_executor.py --json-report .cache/tag-release-tests.json` | 36 passed，0 skipped；未连接生产 |
| OpenSpec严格校验 | `openspec validate unify-card-tags --strict` | 通过 |

Python环境使用本worktree的uv虚拟环境，前端依赖按锁文件安装。工具运行均使用当前worktree，不调用主仓库应用。CI创建独占6179/6180，端口被占用则拒绝，不接管已有实例；最终后端报告确认两个实例已停止。浏览器使用独占6179和24568，与清库测试顺序执行。

早期失败与复测：旧测试写死迁移版本号及故障注入编号，已更新；Windows长路径导致图片测试失败，CI临时测试路径缩短后全部通过；重名错误响应UUID序列化及延迟约束断言已修复。前端曾有线程未启动和冷启动等待超时，最终浏览器结束后顺序运行79项通过，不将未启动的一轮记为通过。沙盒临时目录权限失败的脚本测试改用worktree内显式临时目录复测。多次浏览器重跑触发注册限流时，仅在核对本次data_directory后重置该一次性库的限流夹具，未修改产品限流规则。

## Migration and Recovery Evidence

新增0007，0001至0006原始字节不修改。同账号NFKC后去首尾空白同名去重；不同账号分别保留；优先既有tag稳定ID，冲突映射另分配ID。旧名称、kind、ID、快照与每条来源关系保留，正常／归档／回收站均回填；30个不同关联及80字符名称有实测。卡片、会话、附件、合集、清单和复习既有保留行为由新旧迁移回归共同验证。

`.cache/card-tests/tag-migration-rehearsal.json`记录迁移约0.062秒、备份恢复约5.38秒（仅小型隔离夹具，不是生产容量承诺）、62条来源关系去重为61条、两个账号隔离、恢复后的旧ID解析及写入、规范标签前向改名后别名仍稳定。旧结构启动拒绝、核验失败／授权失败回滚及重跑均通过。

`.cache/card-tests/tag-query-plans.json`保存1000卡all/any实际执行计划：all计167张，any计667张，稳定分页无重复；本次执行约2.55ms／0.48ms，仅代表隔离夹具。

恢复以兼容包或前向修复优先；旧reference/memo包自动回退被拒绝，同能力且满足既有API／迁移字节门禁的包可恢复。整库恢复须保存故障库、明确备份截点与此后写入处理，禁止破坏性down迁移。详见 `apps/api/TAG_MIGRATION.md`。

本机deploy目录受Git忽略。本worktree复制了所需无凭据工具并验证，未复制target.local.json；可交付的差异保存在 `release-tools.patch`。正式使用前仍需维护者将补丁应用于实际工具项目并核验，此处不发布工具或应用。

## Screenshot Generation

真实Chrome，320、390、1280宽，900高视口。当前清单为 `.cache/frontend-visual-review/unify-card-tags/current/manifest.json`：186张整页／滚动末尾截图，覆盖卡片全部／三类型、备忘四视图、复习、合集／目录、我的、设置标签管理、代表详情、四类编辑、长名／30项／空标签、加载／创建失败／重名／冲突／不可用及混合筛选。键盘Enter／方向键／Escape、滚动末尾及触控由真实用例执行。

## Actual Screenshot Review

已实际查看全部93个页面／状态组合及186张主／末尾证据，覆盖三个宽度，视觉审查通过，无未解决的阅读或操作问题。为避免长图缩小后文字不可读，`scripts/review_tag_screenshots.py`将每张截图完整分块为 `.cache/frontend-visual-review/unify-card-tags/current/review/sheet-*.png`；移动截图保留原像素，桌面以75%展示，index.json记录全部原图／分块坐标，不省略像素。最终96张审查图共320个分块均已查看，`review/viewed-final.json`保存SHA256和源图坐标；逐页面结论见 [visual-review.md](visual-review.md)。2至12号图与前轮已查看版本SHA256一致，其余重新查看；26至33号图在本次最终补拍前查看，其内容未受定向补拍影响。

## Findings and Retest

已发现并修复：无效筛选标签误显示为加载中；键盘高亮项未自动滚入可见区域；复习筛选在320宽工具栏被挤窄；设置页仍有分类管理分栏；快速收录保留旧分类文案。均已构建并更新受影响截图。早期截图捕获了加载中的结果，已等待networkidle并重新生成；Chrome原生fullPage部分长页出现视口外未绘制的截图瑕疵；已补拍137张实际滚动视口截图，manifest保留文件及真实y坐标。审查辅助verified长图按这些实际像素拼接，原始fullPage和视口图均保留；另实际查看原始页首视口确认内容可读。定向视觉用例最终1 passed，补拍后再次查看。

## Uncovered Scope

未执行日常／生产迁移、真实发布、外部网站收录成功率实测或生产大库容量演练。未覆盖其他浏览器、操作系统、额外断点及屏幕阅读器；本次键盘、触控及视觉证据来自Chrome。旧API兼容保留，本次不清理快照／映射，不新增导航或卡片类型。

## Workspace State at Implementation Completion

HEAD仍为上述基线，源码、测试、文档及OpenSpec修改均留在当前worktree，未暂存／提交／归档。`git diff --check`通过；前端lint、build、format:check均通过，构建CSS为index-BC2smKAy.css；候选工作区文档检查114个本地链接、0错误（包含新增文件，不改变Git索引），证据 `.cache/tag-docs-check.json`。OpenSpec严格校验通过。最后浏览器环境browser-4594b73c已通过stop-requested正常关闭，其工具输出确认独占服务与数据库停止。发布工具差异作为release-tools.patch交付，不发布到主项目或外部环境。

## Acceptance and Local Delivery

2026-10-22按用户要求进行验收、同步主规格、归档及本地Git提交，暂不推送、部署或合并main。以上自动测试和截图为实施阶段最终证据，本次应用源码未改变，不重复运行完整应用回归。原任务独立核对最终后端201通过／0失败／0跳过及隔离实例停止报告；96张已查看审查图哈希全部匹配，93组主／末尾及137张视口补拍文件无缺失；抽看sheet-001、040、070、096，未发现新的阻断问题。原任务只抽查这4张，没有声称重新查看全部截图；全部查看由实施任务的记录支撑。缓存viewed-final.json部分中文结论编码不完整，以同目录逐页中文visual-review.md、SHA256和实际查看记录共同核对，不以乱码字段单独判断通过。

主规格unified-card-tags、card-library、card-schema-evolution已按三份delta同步并逐份对照，无剩余差异，原场景保留；任务22/22完成。归档后修正TAG_MIGRATION.md等相对链接，重新检查规格、归档、文档链接及Git差异。发布工具只交付无凭据release-tools.patch，未应用到主仓库或服务器；实际发布前仍须批准工具升级并按操作手册备份、停写和执行0007。主仓库用户未提交的.gitignore、MAINTENANCE.md完全保留。

测试范围说明：201项后端、79项前端包括既有全套回归；新增迁移、兼容、owner隔离及恢复测试源于此次持久模型变更。186张主／末尾截图与额外补拍规模偏重，不作为以后每次修改的最低要求；后续按影响面选择代表页面及状态，三档宽度检查正常布局，错误／冲突等相同结构状态按代表宽度覆盖，末尾或局部截图按风险补充。本次不修改AGENTS或建立新测试政策。

归档提交检查补充：release-tools.patch中的3个单空格行是合法unified diff上下文，不可删除，否则补丁损坏。原格式保留；git apply --stat及在主仓库的git apply --check均通过（只校验，未应用）。其他文件运行完整git diff --cached --check；该补丁单独仅关闭blank-at-eol误报检查，其余检查保留，未更改仓库Git配置。
