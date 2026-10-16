## Context

公开仓库没有workflow，但有冻结锁文件和完整测试。集成夹具固定6179及仓库 `.cache/card-tests`，注册策略夹具另要求6180及 `.cache/registration-policy`；不能直接改用任意数据库容器目录。生产发布工具整体被Git忽略，不可作为公开CI依赖。

## Goals / Non-Goals

**Goals:** 独立docs、frontend、backend三项基础检查，可本地复跑，后端不通过skip获得绿灯。

**Non-Goals:** 本轮不在云端运行Playwright／视觉评分，不接入生产或自动发布，不修改分支保护、业务源码、迁移或现有测试的隔离限制。

## Decisions

- 使用ubuntu-24.04，Node22、项目packageManager固定pnpm10.33.0、Python3.13和固定uv0.11.16；官方Action固定完整提交，contents只读，checkout不持久化凭据。push不限制分支，PR使用pull_request而非pull_request_target，并提供workflow_dispatch。
- PostgreSQL18从官方PGDG apt源安装，辅助脚本以runner普通用户在两个固定缓存前缀下创建唯一目录。使用仅回环的临时trust认证与合成角色密码，匹配现有夹具中不带密码的管理员及迁移演练连接；不开放外部接口，不复用真实数据。
- 后端脚本先检查端口及PG18工具，清除继承的SELFLORE／libpq配置，固定两个实例和目标，bootstrap／migrate开发测试库，顺序运行全部后端测试，解析JUnit并拒绝skip、失败和空结果。finally只停止本次拥有的实例；清理失败同样返回失败。
- 文档检查只用标准库，git ls-files确定交付范围，检查当前非OpenSpec Markdown的本地链接、图片、章节与围栏；不探测外站，不要求历史归档链接仍指向当前目录。用临时Git仓库验证缺文件、锚点、路径逃逸及代码块边界。
- 后端只上传JUnit和汇总JSON，不上传数据库目录、密码文件或业务媒体；前端保留组件测试报告，所有失败维持非零。
- 先以本机环境测试脚本与同等命令，并用actionlint验证workflow；实际Actions是否已触发、成功需另有真实运行证据，不能从静态检查推断。

## Risks / Trade-offs

- [Linux runner与Windows本机差异] → 固定runner与PG版本，辅助脚本跨平台复跑；记录本机未能覆盖的Linux安装和实际Actions结果。
- [SIGKILL不能执行finally] → 临时runner在job结束后回收，脚本不删除离线数据；正常失败与中断处理关闭自有实例。
- [基础CI不覆盖浏览器排版] → 保留原视觉审查约定和本机发布门禁，在公开文档明确边界。
