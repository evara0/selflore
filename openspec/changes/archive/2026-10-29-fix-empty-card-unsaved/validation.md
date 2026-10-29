# 验证记录

- 时间／审查者：2026-10-27，Codex。
- 基线提交：9551d7ee16d930376f6c1830223625f43b5796c9。
- 实施分支／工作区：`fix/empty-card-unsaved`；`E:/261027-selflore-idea/worktrees/fix-empty-card-unsaved`。初次验收时保留未提交的源码、测试与本 change，未修改 main；后续交付授权见文末。
- 桌面 managed worktree 工具因聊天目录不是 Git 仓库而失败，使用 Git 创建普通 worktree；桌面附加工具不支持该普通 worktree。后续操作均显式指定该目录。
- 实现：仅移除 CardForm 类型切换回调中的 `setDirty(true)`，未修改布局或样式。

## 自动检查

| 命令 | 结果 |
| --- | --- |
| `openspec validate fix-empty-card-unsaved --strict` | 通过 |
| `pnpm format:check` | 通过 |
| `pnpm exec prettier --check src/features/cards/CardForm.tsx e2e/editor-boundaries.spec.ts` | 通过 |
| `pnpm lint` | 通过 |
| `pnpm test` | 10 个文件、81 项通过 |
| `pnpm build` | TypeScript 与 Vite 构建通过 |
| `pnpm exec playwright test e2e/editor-boundaries.spec.ts --grep 'card type choices'` | 最终 6 项通过 |
| `git diff --check` | 通过 |

浏览器回归使用当前 worktree 构建的 dist，通过本地 24569 预览及内存 API 替身运行，不接触业务数据库。空白用例从 knowledge、opinion、reference 三种入口进入，逐一切换并重复点击三个类型，再用键盘 Enter 进入备忘，断言无弹窗和无写请求。标题、问题和来源作者分别验证真实输入后跨类型切换仍有确认，取消后输入保留，接受后进入备忘。

初次运行 5 通过、1 失败：问题字段重新挂载后 `getByLabel` 精确定位失败，页面快照显示值仍保留。改用 textbox 的可访问名称定位，复测 6 项通过。没有为此增加产品修改。首次格式检查发现测试格式问题，已用 Prettier 修正并复检通过。

## 前端视觉审查

- 浏览器：Chrome 155.0.8059.85，Playwright 1.63.0，Windows，无头浏览器。
- 数据：测试内存合成账号与标签；空白新建资料卡及普通备忘。
- 当前构建生成后未再修改产品代码；后续仅调整测试定位与截图滚动方法。
- 截图保留目录：`E:/261027-selflore-idea/selflore/.cache/recovered-worktrees/fix-empty-card-unsaved/frontend-visual-review/fix-empty-card-unsaved/`，下表文件均在此目录。原 worktree 缓存已完整复制并逐文件 SHA-256 核对，回收 worktree 后仍可查看。

| 路由／状态 | 视口 | 截图文件 | 已生成 | 已实际查看 | 结论 |
| --- | --- | --- | --- | --- | --- |
| /new?kind=knowledge，本地切换至空白资料卡 | 320×844 | new-card-320-blank.png | 是 | 是 | 所查范围未发现问题，类型标签可换行 |
| 同上 | 390×844 | new-card-390-blank.png | 是 | 是 | 所查范围未发现问题 |
| 同上 | 1280×844 | new-card-1280-blank.png | 是 | 是 | 所查范围未发现问题 |
| /new?kind=memo，空白普通备忘 | 320×844 | new-memo-320-blank.png | 是 | 是 | 所查范围未发现问题 |
| 同上 | 390×844 | new-memo-390-blank.png | 是 | 是 | 所查范围未发现问题 |
| 同上 | 1280×844 | new-memo-1280-blank.png | 是 | 是 | 所查范围未发现问题 |
| /new?kind=memo，滚动至保存区域 | 320×844 | new-memo-320-footer.png | 是 | 是 | 保存按钮可达，居中滚动后不受底栏遮挡 |
| 同上 | 390×844 | new-memo-390-footer.png | 是 | 是 | 保存按钮可达，居中滚动后不受底栏遮挡 |
| 同上 | 1280×844 | new-memo-1280-footer.png | 是 | 是 | 所查范围未发现问题 |

- 交互：在三个宽度使用键盘聚焦备忘链接并 Enter；滚动至备忘保存按钮并断言在视口内。已查看保存按钮区域的最终截图。
- 问题与复测：最初 scrollIntoViewIfNeeded 截图未实际展示窄屏保存按钮，改用立即居中滚动重新运行，实际查看最终截图，按钮显示完整；无需产品修改。
- 未覆盖：真实手机键盘、安全区、其他浏览器、侧栏最末端、新建清单内部编辑、附件上传、后端接口与完整已有浏览器套件。本次变更仅涉及卡片类型事件，不以此抽样宣称全站视觉通过。
- 结论：自动回归通过；截图已生成并实际查看，已审查范围内未发现排版问题，无待处理的本次范围内视觉问题。

## 交付准备

2026-10-27，用户授权提交、合并、推送并回收 worktree。main 已先交付文档整理提交 5263012，fetch 后与 origin/main 为 0 / 0；该文档提交不影响修复涉及的产品代码和测试。交付前复核本变更源码、浏览器用例、全部任务及上述验收记录，OpenSpec 严格验证和 diff 检查通过。沿用已通过的 81 项组件测试、6 项定向浏览器测试及九张实际查看截图，不将其表述为完整浏览器套件或后端验证。

先将本 worktree 的 .cache 完整保留到主工作区的 .cache/recovered-worktrees/fix-empty-card-unsaved，并逐文件校验一致；依赖与 dist 为可重新生成产物。修复提交后合并 main，核对合并结果只增加修复、测试及本变更记录；推送成功后移除已干净且已合并的普通 worktree。Git 提交、合并和远端结果以最终交付输出为准。此次不操作生产发布。

## 2026-10-29 归档前复核

- 代码基线：main，37cc76d55144e9f1837fb4e51a1dba8d70e6d32b；本轮只更新主规范及归档记录，没有修改产品源码、样式、测试或依赖。
- 规划：proposal、specs、design、tasks 均为 done，5 项任务全部完成。
- 自动测试：当前合并代码 pnpm test 通过（12 个文件、89 项）；pnpm format:check、pnpm lint、pnpm build 均通过；定向 Playwright 回归 e2e/editor-boundaries.spec.ts --grep 'card type choices' 6 项通过。
- OpenSpec：归档前变更严格校验通过；主规范严格校验 32 项通过。card-workspace 同步新增要求“空白新卡片类型选择不触发离开保护”及两个场景，逐字核对同步完整，保留其他要求。
- 浏览器：Playwright 使用 channel=chrome；当前构建由本机 127.0.0.1:24569 提供，内存 API 替身和合成账号，不连接业务库。
- 截图生成：G:/selflore/.cache/frontend-visual-review/2026-10-29-fix-empty-card-unsaved-archive/，三个视口分别为 320×844、390×844、1280×844。
- 截图实际查看：new-card-320-blank.png、new-memo-320-blank.png、new-memo-320-footer.png；new-card-390-blank.png、new-memo-390-blank.png、new-memo-390-footer.png；new-card-1280-blank.png、new-memo-1280-blank.png、new-memo-1280-footer.png，共 9 张均通过图像工具逐张实际查看。
- 视觉结论：所查空白资料卡、普通备忘首屏和保存区域文字可读、控件对齐，320 宽度类型选项正常换行；滚动后的保存按钮完整可达，没有本轮范围内待处理视觉问题。未修改产品展示代码，无需修复复测。
- 交互：三种宽度的空白跨类型及重复点击不触发离开确认，键盘 Enter 可进入备忘；标题、问题和来源作者实际输入后，取消离开保留内容，确认离开进入备忘。
- 未覆盖：真实手机键盘及安全区、其他浏览器、侧栏最末端、完整浏览器套件、后端及生产环境；不宣称全站视觉或完整系统验证通过。
- 用户已明确授权验证、同步及归档；本轮未自动提交或推送归档文件。
