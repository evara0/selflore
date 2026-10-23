# GitHub展示与协作入口验收

2026-10-16，输入提交`ca37544558761b8dbee8819f80fb0ecb1e624da5`。用户明确选择Apache-2.0；本轮仅修改仓库文档、协作模板、许可证及公开截图，没有改动应用源码、依赖、迁移、CI工作流或GitHub在线设置。

## 交付与自动校验

- LICENSE为[Apache官方完整文本](https://www.apache.org/licenses/LICENSE-2.0.txt)，11358字节，SHA-256为`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`，下载后和落盘校验一致；README及CONTRIBUTING声明Apache-2.0，保留第三方及用户材料的权利范围。
- README新增实际main分支CI状态徽章、两张界面预览、截图来源、贡献及反馈入口。CONTRIBUTING链接已有启动、测试、CI、OpenSpec和视觉审查说明，没有复制维护者私有部署步骤。
- 两个Issue表单经YAML解析核对name／description／body、字段类型、唯一id、label及必填布尔值；不预设标签、评审人或项目。普通Issue入口保留。PR模板包含变化、验证、视觉证据及未覆盖范围，贡献链接使用完整GitHub地址以适应PR正文上下文。字段规则参考[GitHub官方表单语法](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)。
- 106个当前公开Markdown本地链接检查通过；新文件已用Git intent-to-add纳入检查范围，尚未暂存文件内容。公开图片未被忽略，原有docs和临时浏览器材料仍被忽略。
- 当前前端TypeScript／Vite构建通过；CSS构建产物SHA-256为`571cb8e6a17553a4d3f64fc5b19326e508ef38b85c7b50ab3df06cb1f9c09c1f`。本轮没有逻辑变化，未重复运行Vitest、pytest或业务E2E。
- OpenSpec严格验证与Git diff空白检查通过；核对`apps/`、`scripts/`、CI工作流及忽略规则相对输入提交均无变化，任务5/5完成。

## 截图生成与实际查看

Chrome155.0.8059.40，Windows，新浏览器上下文，设备缩放比1，`zh-CN`及Asia/Shanghai；只访问自有127.0.0.1:24569临时构建预览。每个上下文只有两项GET认证请求，由本地替身返回未登录及注册配置；所有卡片和统计来自原生游客演示。未读取真实账号、数据库、用户图片或浏览器已有会话。

| 路由／状态 | 视口 | 公开图片 | 已生成 | 已实际查看 | 结论 |
| --- | --- | --- | --- | --- | --- |
| `/cards?type=all`／游客 | 1280×900 | `assets/screenshots/cards-desktop.png` | 是 | 是 | 当前四导航、分类及资料／观点示例可见，无页面横向溢出；保留现有分类名称换行 |
| `/memos`／游客 | 390×844 | `assets/screenshots/memos-mobile.png` | 是 | 是 | 页头品牌与署名同行，清单卡可读，移动四导航及中央新建可见 |

两张图片均已通过图像查看工具实际打开，没有以文件存在或DOM断言代替查看。按标题、示例卡片及字体就绪再截图。总计125020字节；SHA-256分别为`4d7cab7205415c2f969238f3b8e86d8add2bfdf25351f74924346f41852509e4`、`bf06256e87fbd798ea327e244b9f211b7940177ee2cc196ae562d39231ac3672`。生成记录及一次性脚本位于忽略的`.cache/github-presentation/`，公开来源说明位于`assets/screenshots/README.md`。

本轮没有修改产品展示代码，截图用于README展示，完整产品视觉回归不适用。没有将这两张首屏截图宣称为全站视觉通过；未检查320宽、真实手机、登录状态、滚动末尾或交互回归。GitHub页面实际渲染及模板新建流程尚未验证，需相关文件推送后生效；没有创建外部Issue或PR。

## 交付状态

实施验收完成时尚未提交、推送、归档或部署。2026-10-16用户随后明确授权提交并推送到远端，暂不部署；此次同步同时包含此前本地提交`ca37544`的移动端署名调整。GitHub模板及文档的本地验证不代表远端实际渲染或CI结果；推送后另行核对。变更保留未归档，移动端署名调整继续待下一次正式发布。
