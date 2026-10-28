# JSON 导入验收记录

## 环境与交付状态

- 日期／执行者：2026-10-28，Codex。
- 基线：0159d805df9f6be2fb30c0abff916cb6a3900822。
- 实施 worktree：`E:/261027-selflore-idea/worktrees/json-card-import`，分支 `feat/json-card-import`。初次验收后保留暂存，用户随后授权验证、归档、合并和提交，交付复核见文末；未授权推送或部署。
- 主项目：`E:/261027-selflore-idea/selflore`。main 与 origin/main 在创建前 fetch 后为 0 / 0，无未完成操作或子模块；独立分支跟踪 origin/main，创建 OpenSpec 前再次 fetch 并核对 0 / 0、工作区干净，无需 pull。
- 桌面 managed worktree 工具拒绝嵌套仓库 sourceRoot，使用 Git 原生 worktree；所有实施及验证命令显式指定独立目录。未创建新 skill 或 hook。
- 前端：锁定 pnpm 10.33.0；后端：CPython 3.13.2，使用本 worktree 的 .cache/test-runtime 安装 uv 工具，再在 apps/api 冻结同步 .venv；未修改全局依赖、锁文件、数据库或私有部署工具。

## 已完成行为

全局“新建”中的“手动新建／JSON 导入”导航连接 /new 与 /import。导入从 JSON 自带 kind、form 和 memo_format 识别类别，不依赖类别编辑器。支持单对象 UTF-8 文件、BOM 和粘贴；最大 1 MiB。预览接口复用 CardContent 校验并补齐清单行 ID，不写业务表；缺少类别、重复字段、非法结构、无效编码、未知字段及不合法内容均可报错。确认保存复用原创建 API；失败保留输入及预览，重试沿用相同请求／行 ID；修改文本使预览失效；保存后进入 cards 或 memos 详情。

用户的三列需求清单已完整写入 public/examples/paper-reading-checklist.json：十一行、三个列名、目标、理想流程、三个待定细节及首轮验收说明保留。所有条目默认未完成，“必须”“已明确”等文字仅为第三列内容。

## 自动检查

| 项目／命令 | 结果及覆盖 |
| --- | --- |
| `pnpm format:check` | 最终通过 |
| `pnpm exec prettier --check e2e/json-import.spec.ts` | 最终通过 |
| `pnpm lint` | 最终通过 |
| `pnpm build` | 最终 TypeScript／Vite 构建通过 |
| `pnpm test -- src/json-import.test.tsx src/guest.test.tsx` | 此调用实际运行了全量组件套件：11 文件、86 项通过；后续对修改点使用下项定向复测 |
| `pnpm exec vitest run --pool=threads --maxWorkers=1 src/json-import.test.tsx src/guest.test.tsx` | 最终 2 文件、16 项通过：入口、门禁、预览无创建、修改失效、原稿保留、幂等重试及离开保护 |
| `.venv/Scripts/python.exe -m pytest -q tests/test_card_import.py tests/test_memo_schema.py`（apps/api） | 最终 28 项通过，无跳过；六种形式、完整样例、语法／结构／字段／大小／Unicode、重复键、行 ID、鉴权、无业务 DB 访问以及创建请求契约 |
| `python -m compileall -q app/services/card_import.py tests/import_preview_server.py`（API .venv） | 通过 |
| `pnpm exec playwright test e2e/editor-boundaries.spec.ts e2e/json-import.spec.ts` | 同轮现有编辑边界 15 项通过；新增 3 个文件读取用例因 CRLF 断言失败，另 7 项通过，修正后见下项 |
| `pnpm exec playwright test e2e/json-import.spec.ts` | 最终 10 项通过，无失败、跳过或重试：三宽度完整清单导入、六种形式跳转、失败重试、门禁、离开保护、预览失效、大小、无效 UTF-8、有效 BOM 与替换字符 |
| `python scripts/check_docs.py` | 122 个当前公开本地链接／锚点，0 错误 |
| `openspec validate add-global-json-card-import --strict` | 通过 |
| `git diff --cached --check`、`git diff --check` | 通过 |

后端测试有现有锁定 Starlette/TestClient 关于 httpx 与 BlockingPortal 的两条弃用警告，不影响结果；没有升级依赖来消除警告。

浏览器运行已构建的本地 24569 前端，预览请求通过用例临时启动的环回随机端口 FastAPI 服务执行真实校验。合成身份有 Origin／CSRF 校验，夹具明确清空应用 DSN 并拒绝业务数据库连接，创建由浏览器内存替身处理。测试进程在套件结束后关闭自己的服务；没有写入日常 6171、一次性数据库或生产。

## 问题与复测

1. 首次新增测试后的构建发现 Testing Library 的 ByRoleOptions 不支持 exact 选项；移除该测试选项后最终类型构建通过，未改变产品逻辑。
2. 后端曾错误指定不存在的 test_reference_schema.py，导致该次零测试；纠正为实际存在的 test_card_import.py 与 test_memo_schema.py 后最终 28 项通过，不把零测试记录为通过。
3. 第一轮截图中示例正文的加粗界定符与后续中文连写，导致星号原样显示；在示例中补段落分隔，重新构建、运行及查看最终截图。同步将常见字段错误改为中文，同时保留字段定位。
4. Git 加入索引后，Windows 工作区样例使用 CRLF；HTML textarea 的值按标准转为 LF，浏览器精确字符串断言失败但 JSON 内容相同。只修正测试预期的换行规范化，没有放宽字段／条目断言或修改产品；最终十项全部通过。
5. 浏览器版本查询初次经 pnpm.CMD 的内联引号转义失败，改用 Node stdin 正常查得版本；不影响应用或上述测试。

## 前端视觉审查

- 浏览器：Chrome 155.0.8059.85，Playwright 1.63.0，Windows，无头模式。
- 数据：合成账号、默认空白知识卡；用户提供的完整三列需求、缺少 kind 的对象、合成503保存失败。
- 最终构建产物：JsonImport-opUCGoqB.js（SHA-256 `377a4e8f365a4cc200992aa4cea1152d3f472e6bc6354527e755e5044e074ce9`）；index-CYojr_fq.css（`ee783d355b099fd96bbc82fef4ad671600bff9a75ce0e844915fc7a077c11052`）；构建后的样例 JSON（`3050b955e3be10073c1fb1803dd5de8d7eb19475b9ce25a35a76a611c028a902`）。
- 最终截图目录：`E:/261027-selflore-idea/worktrees/json-card-import/.cache/frontend-visual-review/json-import-final/`。下表18个文件均已生成，并通过图像查看工具逐张实际打开查看；旧 json-import 目录的截图不作为最终验收。

| 页面／状态 | 320×844 | 390×844 | 1280×844 | 查看及视觉结论 |
| --- | --- | --- | --- | --- |
| /new，手动新建与全局模式导航 | import-320-manual.png | import-390-manual.png | import-1280-manual.png | 均已查看，标签换行和输入框对齐正常 |
| /import，空状态及文件入口 | import-320-empty.png | import-390-empty.png | import-1280-empty.png | 均已查看，文件控件和描述可读，无裁切 |
| /import，缺少类别错误 | import-320-invalid.png | import-390-invalid.png | import-1280-invalid.png | 均已查看，中文错误可读，原输入保留 |
| /import，目标和流程预览 | import-320-preview.png | import-390-preview.png | import-1280-preview.png | 均已查看，加粗分段修复；正文可换行，桌面双栏、窄屏单栏 |
| /import，三字段条目 | import-320-columns.png | import-390-columns.png | import-1280-columns.png | 均已查看，桌面三列；窄屏按字段分行，长中文无局部裁切 |
| /import，末尾失败与确认按钮 | import-320-retry.png | import-390-retry.png | import-1280-retry.png | 均已查看，错误靠近操作，按钮可滚动到达且不被固定底栏遮挡 |

实际交互：文件上传、粘贴、校验后焦点到达预览标题、滚动到最后一行与确认按钮、确认按钮键盘 Enter 保存、取消离开保留草稿。整页宽度断言作为辅助，未拿它替代截图查看。生成的既有来源功能等额外截图未作为本次视觉证据；本次范围是共享新建方式导航及新导入页面，没有更改全局字体和主导航。

结论：18 张最终截图均实际查看，已审查范围内未发现未解决的阅读、操作或排版问题。没有数值测量颜色对比度，不宣称达到特定对比度标准。

## 未覆盖及限制

- 未执行真实账号／数据库完整创建闭环、全量后端或全量真实接口浏览器套件；已有创建事务、幂等和所有权逻辑复用，没有在此报告中宣称重新验证。
- 未检查真实安卓键盘、安全区、其他浏览器、200行极限布局、跨账号／跨实例附件或标签导入；账号归属与可用性仍以实际保存结果为准。
- 未保存草稿仅在当前页面状态中保留；刷新、关闭、退出或会话失效导致页面卸载不保证恢复。没有新增本地持久化或跨账号缓存。
- 首版每份一个对象，不支持批量、合集、导出恢复或自动下载图片。初次实施阶段未修改 main，后续按用户明确授权合并；没有部署到运行环境。

## 2026-10-28 归档与合并前复核

用户明确要求“验证归档合并提交”。复核 main 工作区干净，fetch 后 main 与 origin/main 为 0 / 0，未发现需要拉取或合并的远端变化。本次依次执行本地归档、提交及合并，不推送或部署；提交结果由最终 Git 状态确认。

- 重新运行 format:check、lint、TypeScript／Vite build：通过。
- 重新运行全量组件测试：11 个文件、86 项通过。
- 重新运行 test_card_import.py 与 test_memo_schema.py：28 项通过，0 跳过，仍有上述两条依赖弃用警告。
- 同轮执行 editor-boundaries.spec.ts 与 json-import.spec.ts：25 项通过，0 失败／跳过／重试，用时42.6秒。
- 当前公开文档检查：122 个本地链接，0 错误；变更严格校验、Git 暂存差异检查通过。
- 重建的产品 JS 和 CSS 摘要与本报告18张已实际查看截图对应的构建一致，截图文件完整保留；构建的样例 JSON 与源文件解析后相同。因此沿用上述视觉结论，不把本轮自动生成的 json-import-acceptance 截图宣称为已经逐张查看。
- 不改产品源码和样式，归档时同步 json-card-import 主规范并补齐 Purpose；归档后检查主规范和文档链接。
- 本次验证仍使用真实预览 API 与合成创建替身，没有业务数据库或生产副作用。保留工作树及截图供审查，不回收 worktree。
