# 资料卡快速收录验收

日期：2026-10-19。基于提交`9e929d443afab243aa2134ad60be5824115c1a08`的未提交工作区实施；实际基线完整SHA以本次manifest.json为准。以上为实施阶段基线；2026-10-19按用户后续要求同步主规格、归档并进行本地Git提交，暂不推送或部署。

## 自动验证

| 检查 | 最终结果 |
| --- | --- |
| API针对回归：test_source_capture.py、test_health.py、test_frontend.py | 41通过，0跳过；包括36项来源解析／安全／鉴权测试，保留2条既有依赖弃用警告 |
| 前端Vitest | 8文件，75项全部通过；最终17.62秒 |
| 格式、Oxlint、TypeScript／Vite构建 | 通过，使用前端目录锁定的pnpm10.33.0 |
| editor-boundaries.spec.ts真实Chrome | 9项全部通过，最终9.8秒；全部API读写使用合成替身，未连接业务库 |
| 文档 | 111本地链接，0错误；新增文档使用git intent-to-add纳入检查，未暂存文件内容 |
| package.json | 严格重复键检测通过；format、format:check各一项，命令未变 |
| OpenSpec／diff | 严格校验及空白检查通过 |

首次API命令从错误目录运行导致导入失败，已改到apps/api。首次Vitest工作线程启动超时，随后高负载下既有游客登录测试出现懒加载页超出默认1秒等待；单独复测正常。为该断言设置与现有首个懒加载等待一致的5秒预算，保留登录、过期及私人数据隔离断言，最终完整75项通过。根目录调用pnpm --dir选择了全局版本，收尾改为前端cwd使用锁定版本，不更改依赖或绕过版本校验。

浏览器初次“获取方式”精确标签定位失败，控件已补明确aria-label。追加已有资料测试时，textarea初始文本影响getByLabel精确匹配，改为真实textbox角色及可访问名称定位；合成图片配置补齐像素与最长边，避免替身显示NaN。最终全部浏览器回归通过。

## 真实联网结果

最终后端只读实测保存在[network.json](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/network.json)：普通网页https://ogp.me/在0.73秒获取标题，状态partial（作者等未知不猜测）。用户给定X链接的免费专用方式timeout，随后网页方式也timeout，总12.54秒，返回category=x、method=webpage、status=unavailable、空建议。说明回退真实执行，但不声称该推文已成功解析；X成功字段映射通过固定公开格式替身验证。没有调用付费API、使用X登录态或第三方镜像。

## 后续一次性代理验证

2026-10-19按用户要求，临时使用`http://127.0.0.1:7897` HTTP代理读取同一X链接。官方oEmbed返回HTTP200、1001字节、0.62秒，提取作者Andrej Karpathy与推文文本；普通网页返回HTTP200、181989字节、1.65秒，提取页面标题、平台及2026-10-11发布日期。采用内存urllib请求并复用现有纯解析函数，没有修改应用代码、环境配置或持久代理设置，没有将推文保存到业务库。

这与上节直连失败结果并存：代理路径可用不代表当前应用抓取器可用，也不能据此修改现有直连验收结论。用户决定代理支持低优先级暂缓，仅在design及使用说明记录问题、影响范围和提升优先级条件。本次记录为纯文档变更，无展示影响，新增视觉审查不适用；此前10图及测试属于功能实施阶段，未重新运行应用测试。

## 截图生成与实际查看

Chrome155.0.8059.82，Windows，127.0.0.1:24569，320×900、390×900、1280×900；使用合成会员fixture_user及演示资料，无私人数据。每次截图前等待页面状态与字体就绪。最后一轮所有下列10张PNG均已通过图像查看工具实际打开，未用文件存在、DOM或Vitest替代查看。

| 路由／状态 | 320 | 390 | 1280 | 已生成／实际查看及视觉结论 |
| --- | --- | --- | --- | --- |
| /new?kind=reference，输入链接 | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-320-ready.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-390-ready.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-1280-ready.png) | 全部是；控件及文字在容器内，桌面操作对齐 |
| 同页，X回退并部分补全 | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-320-fallback.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-390-fallback.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-1280-fallback.png) | 全部是；提示正常换行，未盖住后续输入 |
| 同页，请求错误 | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-320-error.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-390-error.png) | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/capture-1280-error.png) | 全部是；重试可用，输入保留 |
| /cards/演示资料ID/edit，无可用元信息 | 未抽查 | [图](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/existing-390-unavailable.png) | 未抽查 | 是；已有资料色彩及提示可读，内容保留 |

最终构建为`index-7W_jqCxK.css`及`Editor-CP1_W6ZB.js`等；精确构建文件、源码输入及10图SHA256见[manifest.json](../../../../.cache/frontend-visual-review/2026-10-19-quick-capture/manifest.json)。最后展示代码变动后重新构建、截图、全部查看；之后只修改测试、文档和网络读取逻辑。

## 问题、处理与复测

| 问题 | 处理／最终复测 |
| --- | --- |
| 新模块标签继承全局外边距，桌面按钮与下拉框底边不齐 | 限定source-capture内标签margin为0，重建并查看三档截图，已对齐 |
| 模块最初使用不存在的边框变量 | 改用主题已有border变量；三档边界明确且不引入全局样式变化 |
| 窄屏输入框及下拉框局部伸出模块边缘，整页却无溢出 | scoped宽度100%及border-box修复；新增逐控件边界断言，三档截图复看均在容器内 |
| 请求中主动清空字段可能再次被补空建议填入 | 记录手动触碰，浏览器验证作者清空保持空、卡片标题和明确发布者仍可补全 |

浏览器实际执行：收录链接Tab至获取方式；滚动到保存控件并成功点击，失败后再次保存进入资料详情；现有内容和请求中编辑保留；新建知识页不显示收录模块。模块控件边界与整页横向宽度均单独断言。短视口截图中后续表单可继续滚动；不是以首屏显示全部内容作为标准。

已审查范围内未发现未解决的阅读或操作问题。未实测真实手机键盘／安全区、其他浏览器、所有网站和登录墙、多进程统一限流、完整真实数据库与生产闭环；既有上传本次只验证保留，不重新执行完整上传。无新对比度数值测量，不作全站或免费平台成功率保证。无数据库或API依赖变更，后端完整数据库套件未运行。

## 归档交付

2026-10-19用户明确要求归档并本地提交。新增主规格已核对3项需求及6个场景与delta一致，无剩余同步内容；任务6/6完成，归档目录为2026-10-19-add-reference-quick-capture。代理支持暂缓决定随代码、说明和一次性实测记录一并纳入本地提交，不实施代理配置。此次只同步规格及移动文档，不更改已验收的应用源码，沿用上述自动测试和已实际查看的10图；重新执行归档／规格校验、公开文档链接及Git差异检查。截图与网络JSON为本机忽略证据，不随Git交付。
