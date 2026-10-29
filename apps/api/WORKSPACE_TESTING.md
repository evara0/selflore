# 本地验证与隔离测试

## 前端视觉审查

影响前端展示的变更，完成前必须在真实浏览器检查并实际查看截图。Vitest检查逻辑与交互，Playwright检查已声明的浏览器行为和部分布局；两者通过不代表排版可读。当前截图仅留存，不包含自动基准比较、Evals或图像评分。项目规则见[AGENTS.md](../../AGENTS.md)，产品视觉要求见[默认主题规范](../../openspec/specs/default-ui-theme/spec.md)。

### 选择范围

| 变更 | 必查范围 |
| --- | --- |
| 单页面展示 | 该页面及相关详情、编辑、弹窗和状态 |
| 共享组件 | 每种代表用法，尤其长文字、多标签及不同容器宽度 |
| 全局CSS、字体、导航 | 卡片、备忘、合集、我的及代表详情、编辑、认证弹窗；同时检查首屏与末尾 |
| 无展示影响的后端或文档 | 记录不适用及原因，不强制启动浏览器或业务库 |

默认检查320×844、390×844、1280×900视口（CSS像素），窗口高度影响问题时记录实际高度。涉及平板或其他断点时增补；既有主题规格要求的736、1024、1440等尺寸仍须按影响面覆盖。涉及缩放、字体或固定栏时补充相应检查。桌面缩窄窗口不代表已验证真实手机键盘、安全区或其他浏览器，未验证部分如实列出。

使用可复现的合成数据，按变更选择长中文标题、长英文／URL、多标签、长清单、图片、空状态、错误反馈和选中／完成状态。不要机械生成所有页面×所有状态组合，但必须说明代表样本与遗漏。优先使用独立演示或API替身；真实写入仅在下文约定的一次性库，禁止使用日常账号、6171库或用户图片做测试。修改业务数据返回形状时，除展示替身外应执行对应真实接口测试，不能由替身替代。

### 执行与查看

1. 记录变更、代码提交及工作区修改、浏览器版本、路由、视口、数据和状态。运行适用的lint、类型构建、组件和浏览器测试；流程说明变更不必跑完整应用回归。
2. 使用当前代码构建。执行下文浏览器流程或已明确路由／数据的只读浏览器检查；沿用现有测试命令，不新增假定存在的视觉测试命令。等待页面加载、字体与图片就绪再截图，不使用任意固定等待代替就绪判断。
3. 将新截图保存到独立运行目录，例如`.cache/frontend-visual-review/<run-id>/`。既有测试可能输出到docs或其他缓存目录，报告引用实际路径。截图名包含页面、视口与状态；记录构建产物或输入摘要，避免误用旧图。
4. **实际打开并查看每张用于验收的截图。** 全页图用于检查整体结构；密集文字、控件对齐和可疑区域使用原尺寸视口图或局部图确认。记录查看过的文件，而非仅列出生成目录。由Codex审查时使用图像查看工具读取图片，不把DOM断言或文件存在视为已经看过。
5. 在浏览器滚动至内容末尾，检查固定栏、分页和最后一个操作；相关交互以键盘或触控验证。截图无法证明的操作单独记录实际检查结果。
6. 对问题定位并复测。修复后重新构建并生成新证据；审查后再次修改展示代码，相应页面需要重查。纯审查任务记录待修复项，本次无需扩大为产品改动。

### 查看清单与结果

- 文字：有无位置偏移、局部裁切、意外截断、行高不足、长链接挤压、难读字号或密度。
- 布局：标题、图标、标签、输入框与按钮是否对齐；间距是否协调；是否出现不合理空白、重叠或装饰覆盖。
- 可读性：正文、次要文字、选中／禁用／错误状态是否可辨。对比度数值只能来自实际测量，不能凭截图宣称达到4.5:1。
- 可达性：移动导航、弹窗、固定栏是否遮挡正文或操作；末尾内容可滚动到达；相关键盘焦点可见、控件可操作。
- 内容：长标题、多标签、图片、清单及空／错误状态是否保留层级；不能以整页无横向滚动推断局部无裁切。

问题分别标记为阻断操作／阅读、影响可读性、一般排版建议。前两类未处理不能宣称视觉通过；一般建议也应记录处理决定。结论使用“已审查范围内未发现问题”“存在未解决问题”“未验证”“不适用”，不要把抽样检查写成全站保证。浏览器或环境失败时说明原因和未完成范围，不能借旧截图补成功。生成成功但没看过的截图必须标为查看未完成。

### 报告模板

将验收摘要写入对应change的validation.md；截图、局部图和运行日志保留在忽略目录。规则不是自动门禁，实施者必须检查报告与证据是否对应当前代码。

```markdown
# 前端视觉审查记录
- 变更／时间／审查者：
- 提交／工作区状态／构建输入或产物摘要：
- 浏览器／数据来源／环境：
- 自动检查及结果（未执行单独标明）：

| 路由／状态 | 视口 | 截图路径 | 已生成 | 已实际查看 | 视觉结论 |
| --- | --- | --- | --- | --- | --- |

| 问题 | 页面／视口／区域 | 影响与复现 | 截图证据 | 处理／复测 |
| --- | --- | --- | --- | --- |

- 滚动末尾、键盘／触控等实际检查：
- 未覆盖范围及原因：
- 总结：流程执行情况与产品视觉结果分别陈述；不适用时写原因。
```

## 仓库自动 CI

仓库工作流为 `.github/workflows/ci.yml`，分支push、pull_request及手动workflow_dispatch触发；同一事件／分支的新运行取消旧运行。GitHub会在工作流提交推送后执行，手动入口需该文件已在默认分支。触发语义见[GitHub工作流说明](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。

| 检查名 | 自动执行范围 |
| --- | --- |
| Docs and CI tools | CI辅助脚本测试；当前受Git跟踪、非OpenSpec Markdown的本地文件／图片链接及章节锚点 |
| Frontend checks | 锁定pnpm安装、Prettier格式检查、Oxlint、Vitest组件测试及TypeScript／Vite构建 |
| Backend tests (PostgreSQL 18) | 锁定uv安装；自建6179和6180空实例，运行全部公开后端pytest，并拒绝失败、skip或零测试报告 |

三个job独立运行，使用固定提交的Action、只读仓库权限和临时runner；不需要配置生产Secrets，不运行本机deploy工具。此工作流不设置分支保护，是否将检查设为合并必需项由仓库维护者另外配置。

后端PG18通过[官方PGDG源](https://www.postgresql.org/download/linux/ubuntu/)安装。临时实例在项目缓存中创建唯一目录，仅监听127.0.0.1，用trust认证兼容既有测试夹具；它们只有合成数据，不能改用已有实例或开放外部监听。脚本会清除继承的app／libpq连接设置，拒绝占用端口；结束或失败时停止所属实例，清理失败也判失败。强制终止时由临时runner回收环境，本地被强杀的残留实例需按具体缓存目录核对后停止。

以下命令在仓库根复跑辅助检查，无需数据库：

```powershell
python -m unittest discover -s scripts/tests -v
python scripts/check_docs.py
```

文档检查只检查Git交付的当前说明，不探测外站可用性，也不检查历史OpenSpec链接。新文档或链接目标尚未加入Git索引时会失败；应先核对交付范围，不把忽略资料强行加入仓库。普通行内链接、图片、显式引用式链接与Markdown标题锚点受检，外站、HTML自定义锚点和其他扩展语法不作可用性保证。

完整后端CI入口使用已冻结同步的API虚拟环境；在 `apps/api` 执行，`SELFLORE_PG_BIN` 须先设置为本机PG18的bin目录，不能改目标端口：

```powershell
uv run --frozen --no-env-file python ../../scripts/ci_backend.py
```

该命令创建并停止自己的测试库，不需要预建6179／6180；两端口被占用则拒绝。报告保存在 `.cache/ci-reports/backend-<run-id>.xml` 和同名JSON；GitHub仅上传这些报告以及前端JUnit，保留7天，不上传数据库、凭据或媒体目录。

基础CI不自动运行Playwright、实际截图查看、生产备份或部署；这些仍按下文及现有发布门禁执行。CI绿灯不能替代视觉验收。本地命令通过与真实GitHub job通过需分别记录。

## 常规检查

在 `apps/api` 执行 `uv sync --frozen`、`uv run pytest -q`；未提供隔离环境时数据库集成测试会明确skip，不能视为完整通过。前端命令统一见[前端检查与构建](../web/README.md#检查与构建)，Vitest配置为threads／单worker。

## 数据库集成测试

测试夹具会清空身份和业务表，**只允许自行准备的一次性6179实例**，禁止使用6171开发库或生产库。迁移演练额外核对data_directory位于本项目 `.cache/card-tests`。先用PostgreSQL工具创建该私有实例，再按[数据库初始化](DATABASE_SETUP.md)和[迁移说明](CARD_MIGRATIONS.md)准备dev角色及完整链，所有命令改用6179；不得复用业务库。

在 `apps/api` 的专用测试终端配置：

```powershell
$env:SELFLORE_TEST_ISOLATED = '1'
$env:SELFLORE_TEST_APP_DSN = 'host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app'
$env:SELFLORE_TEST_MIGRATOR_DSN = 'host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_migrator'
uv run pytest -q -p no:cacheprovider --basetemp ../../.cache/card-tests/full-run
```

示例DSN不含密码，按实例认证方式配置本机凭据。测试覆盖事务、修订冲突、关系隔离及增量迁移，不能通过换端口来连接真实业务数据。

### 注册策略专用实例

`tests/test_registration_policy_db.py` 还要求独立的空PostgreSQL 18实例：监听6180，data_directory位于仓库 `.cache/registration-policy`，允许本机测试进程按该测试夹具连接 `postgres` 管理库。该实例不能预先运行通用业务初始化；夹具会自行创建随机密码角色和升级基线。

只有在上述一次性实例准备好后，才在专用测试终端设置 `SELFLORE_POLICY_TEST_ISOLATED=1` 并运行测试。未准备时该组会skip，需要明确记录未覆盖，不能仅凭6179测试通过宣称全量数据库测试完成；不要为了消除skip把它指向已有库。

## 浏览器闭环

先完成6179数据库准备，并按[前端说明](../web/README.md#检查与构建)构建当前页面。浏览器上传测试还需要独立媒体目录；以下命令在 `apps/api` 的专用终端执行：

```powershell
$testRoot = (Resolve-Path ../..).Path
$env:SELFLORE_MEDIA_ROOT = Join-Path $testRoot '.cache/card-tests/browser-media'
$env:SELFLORE_MEDIA_OPS_ROOT = Join-Path $testRoot '.cache/card-tests/browser-media-ops'
uv run python -m app.media_storage --initialize --environment dev --media-root $env:SELFLORE_MEDIA_ROOT --ops-root $env:SELFLORE_MEDIA_OPS_ROOT

$env:SELFLORE_DATABASE_URL = $env:SELFLORE_TEST_APP_DSN
$env:SELFLORE_ENV = 'dev'
$env:SELFLORE_ALLOW_REGISTRATION = 'true'
$env:SELFLORE_ALLOWED_ORIGINS = 'http://127.0.0.1:24568'
uv run uvicorn app.main:app --host 127.0.0.1 --port 24568 --no-access-log
```

`SELFLORE_TEST_APP_DSN` 使用前节的6179配置及凭据；浏览器终端须重新设置或继承明确的测试变量。媒体目录只用于测试，不能填日常用户图片路径。

在另一终端的 `apps/web` 设置 `SELFLORE_TEST_ISOLATED=1`，执行 `pnpm test:e2e`。当前配置使用本机Chrome和24568服务；不要把测试指向演示站点或日常账号。用例会创建测试账号与内容，不能与清理数据库的后端测试同时运行。

真实接口用例还须继承明确的 `SELFLORE_TEST_APP_DSN`，只允许 `host=127.0.0.1 port=6179 dbname=selflore_dev user=selflore_dev_app`；密码可来自该DSN或 `SELFLORE_APP_PASSWORD`，不打印到日志。共用的测试fixture在每例开始前调用[隔离辅助脚本](../../scripts/reset_browser_registration.py)，仅清理该库的本机注册限流桶，不删除账号、会话、内容或登录限流。日常6171、生产及连接重定向参数会被拒绝；纯替身用例无需此fixture。Playwright维持单worker串行，禁止并行共享此库。单个用例仍经过产品的15分钟5次注册限制，专门的浏览器用例验证第六次返回429；不要放宽产品限流来运行测试。发布入口会提供这些隔离变量和API虚拟环境。

失败trace默认位于 `.cache/card-tests/browser-results`，部分用例另向忽略的docs或缓存目录输出截图；报告应写实际生成路径。按本文视觉审查流程另存当前证据，旧截图不能替代新检查。

服务用 `Ctrl+C` 停止；PostgreSQL仅用pg_ctl停止自己创建的确切缓存data_directory，不停止其他实例或清理业务数据。截图、缓存及离线库仍需按私有资料保管。

### 仅前端替身回归

`apps/web/e2e/json-import.spec.ts` 覆盖全局 JSON 导入。先在 `apps/api` 用 `uv sync --frozen` 准备 API 测试依赖，再按本节启动已构建的前端预览。执行 `pnpm exec playwright test e2e/json-import.spec.ts` 时，用例自行启动和关闭只监听127.0.0.1随机端口的 `tests/import_preview_server.py`；默认使用 `apps/api/.venv` 中的 Python，可用 `SELFLORE_API_PYTHON` 指定等价的冻结依赖解释器。夹具覆盖合成登录身份、清空继承的应用DSN，并禁止业务数据库访问；预览使用真实解析服务，最终创建请求留在浏览器测试内存中。

该回归覆盖三种视口的文件／粘贴、完整三列清单、失败幂等重试、六种形式、预览失效、离开保护、登录门禁、文件大小和UTF-8编码。截图写入 SELFLORE_CAPTURE_DIR 或用例visual目录，仍需实际打开查看；后端预览契约另由 `tests/test_card_import.py` 验证。此项不替代真实账号／数据库创建链路。

`apps/web/e2e/editor-boundaries.spec.ts`验证注册登录与退出、资料来源字段与重试、合集创建，以及快速收录的手改保留、回退、失败后保存与320／390／1280布局。请求由测试内存替身处理，不需要业务数据库，也不能替代真实接口闭环。来源端点鉴权、网络安全和解析测试为`apps/api/tests/test_source_capture.py`；真实外站成功率须单独实测。

先按前端说明构建，在`apps/web`的专用终端运行`pnpm exec vite preview --host 127.0.0.1 --port 24569 --strictPort`；在同目录的另一个终端运行：

```powershell
$env:SELFLORE_BROWSER_BASE_URL = 'http://127.0.0.1:24569'
pnpm exec playwright test e2e/editor-boundaries.spec.ts
```

可显式设置`SELFLORE_CAPTURE_DIR`为本次独立截图目录（例如项目`.cache/frontend-visual-review/<run-id>`的绝对路径）；未设置时输出至测试专用visual目录。截图生成后仍须按前文实际打开查看。

测试完成后关闭预览进程，并清除该专用终端中的`SELFLORE_BROWSER_BASE_URL`覆盖；完整浏览器套件仍按前节使用独立24568服务。先完成构建再运行浏览器，避免重建清空dist时读取资源失败。

## 代表性回归与记录

| 范围 | 当前测试入口 |
| --- | --- |
| 备忘接口、约束与升级 | `tests/test_memos.py`、`tests/test_memo_schema.py`、`tests/test_memo_migration.py` |
| 备忘交互与布局 | `apps/web/src/memo.test.tsx`、`apps/web/e2e/memo.spec.ts`、`apps/web/e2e/memo-layout.spec.ts` |
| 认证、卡片、资料、复习及合集 | 后端tests与前端组件／e2e中的对应模块，回归范围按实际变更选择 |

记录本次命令、环境、提交、pass／fail／skip及范围；历史表数和测试数量不作为通过标准。旧备忘联合恢复及其他批次结果已迁至[历史验收记录](../../openspec/changes/archive/2026-10-23-consolidate-public-operations-docs/historical-validation.md)。

## 维护者本机发布门禁

`deploy/`、具体接入配置和 `local-deployment/` 被Git忽略，不随仓库交付，也不是上面公开测试的前提。维护者本机 `deploy/RELEASE_WORKFLOW.md` 负责指定提交、同包检查、备份副本、迁移、激活和实际版本／readiness验证；单独CheckOnly不连接生产。没有这套本机工具的协作者按本文运行公开检查即可，不能把本机执行器模拟结果当成生产已发布。
