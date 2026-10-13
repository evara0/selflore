---
title: 资料卡与图片存储实施验证报告
project: selflore
updated: 2026-10-12
status: 本地实现与隔离验收完成；日常及生产未启用
---

# Validation

## 2026-10-13 发布检查可复现修复

注册策略旧账号升级测试的显式迁移链补齐0005，保留旧账号数据不变及重复迁移为空的断言。图片浏览器测试使用浏览器canvas自行生成640×1280合成PNG，文件选择、粘贴和拖拽复用当次字节；截图使用Playwright的testInfo.outputPath，移除readFile及历史缓存样本依赖。

实际运行`python -B deploy/client.py build --debug-working-tree`，从当前工作区提取干净隔离快照；测试使用执行器所属6179、6180及24568实例，无日常或生产操作。持久记录`local-deployment/releases/20261013011514-683e29ef/report.json`：后端145、前端55、浏览器12、执行器27、数据库备份适配器3项全部通过，失败及skip均为0；静态检查实际扫描31个文件、故意错误探针被拒绝、类型及Vite构建通过。图片闭环完成，mobile-original.png和reference-desktop.png生成于本次Playwright输出目录。

最终状态为diagnostic_not_promotable，promotable=false、commit=null。命令非零退出表示调试产物禁止晋级，检查本身全部通过；不是正式Git提交的发布证据。临时6179、6180及24568监听已停止。两项修复任务完成，未提交、未归档、未发布。下述2026-10-12的结果保留为历史记录，其2项skip已由本次完整隔离验证覆盖。

## Scope

变更为`add-reference-cards-and-local-image-storage`。实现资料卡、私有图片原图／缩略图、来源与独立说明、三类检索／合集／链接、只读诊断、联合备份恢复和不兼容旧包自动回退保护。沿用现有项目入口，不创建个人全局技能或定时任务，不归档、不提交或发布生产。

源码基线HEAD：`75f6a193911991175c88fd6559d5bdb11db4d2be`。验收包含当前未提交／未跟踪的工作目录内容，不是该提交的不可变发布证据；生成包为本地检查产物，不宣称可直接晋级生产。已有未提交的本地启动、备份等改动保持保留。

工具核实：Python 3.13.13、uv 0.11.16、Node v22.22.2、pnpm 10.33.0。uv.lock SHA-256为`978DE8E48308C6EAB6286726314870C283F69C58C159476CD517840E22AAA932`，pnpm-lock.yaml为`C32FB239159549DD19F459FC68BC342994B6C8A42D2AAC46F8BCC9978E51FD70`。

## Results

| 项目 | 结果 | 范围与证据 |
| --- | --- | --- |
| 后端全量 | 142通过、2跳过 | `deploy/publish.ps1 -CheckOnly`在明确的一次性6179库运行；两项旧注册策略测试需要独立6180，未纳入本次资料功能必跑项 |
| 最终兼容回归 | 29通过 | `test_reference_media.py`、`test_workspace_integration.py`、`test_workspace_edges.py`；包含新增的升级前创建请求幂等兼容，不改旧创建摘要，新增不同来源仍409 |
| 前端组件 | 55通过 | `pnpm test`，包含资料类型筛选、选择器标签、失败重试、私人预览释放及游客不访问附件API |
| 静态检查与构建 | 通过 | `pnpm lint`无代码告警，`pnpm build`通过；两个PowerShell入口实际解析成功 |
| 浏览器 | 最终12通过 | 真实Chrome／24568服务，含文件选择、在说明字段粘贴图片、拖入图片、保存、编辑、合集、原图、390像素视图、刷新、退出缓存隔离及旧流程回归；剪贴板测试只派发DOM事件，不修改用户OS剪贴板 |
| 原图及重启 | 通过 | 5个合成附件在API和测试PG重启后原图SHA-256一致、缩略图可读；`restart-media-result.json` |
| 联合恢复 | 通过 | v2包的5个附件、20张表的数据／结构／权限／历史及本人图片读取核验一致；恢复约10.24秒，密码保护隔离实例完成后停止，原测试实例恢复；`media-recovery-result.json` |
| 实际只读诊断 | 通过 | deep检查无严重问题、未登记文件0，识别成功联合备份和恢复耗时；不足7天、24小时窗口／100样本、未提供带宽时明确未知并退出1，未自动清理 |
| 目录和异常 | 通过 | Windows实际Junction被拒绝；原图损坏／缺失、缩略图缺失、上传未完成、空间与权限故障、预算耗尽、身份错误及不越界写报告覆盖；新目录ACL为创建账号与SYSTEM |
| 发布检查与包 | 本地通过 | 当前源码＋构建白名单打包，无业务图片、凭据、数据库、ops日志或备份；能力标记及0005包含于包 |
| 回退保护 | Linux本地模拟通过 | 现有Ubuntu-22.04 WSL执行`deploy/tests/remote-gate.sh`；真实临时发布指针，替身id／sudo／curl，无实际服务或网络操作。未知旧包保持新指针／只一次重启尝试；兼容旧包恢复旧指针／两次尝试；均保留发布失败退出状态 |
| OpenSpec | 严格校验通过 | 保留delta与未归档change；所有任务按实际验证核对 |

联合恢复仅对白名单中的PG18用户名检查完整表达式做等价AND形式归一化；修改长度上限、AND→OR、其他约束或权限仍失败。原始备份签名和历史SQL不改。

## Artifacts

- 最终本地包：`G:/selflore/.cache/releases/reference-media-complete-20261012.tar.gz`，60个条目。
- 包SHA-256：`53A2D80363D18F0B7FB7F5959F85F9D9D1250E26A2A8666E00B6C8C0EAC07035`。
- 远端脚本SHA-256：`FD5AB41AE70FD0A07E00497449128B2ABE84130133C785725A8CBEF0BF1AA203`。
- 私有运行证据目录：`G:/selflore/.cache/card-tests/reference-media-20261012`，含桌面／移动截图、恢复、重启及深度诊断记录；含合成数据的数据库／备份继续私有，不提交Git。
- 回退模拟证据：`G:/selflore/.cache/remote-gate.KeAJfB`，包含假发布包、指针、服务调用次数和失败日志。
- 本报告与变更规划持久保留在OpenSpec change；运行缓存及包并非长期发布账本，清理前按需另存。

## Operation

Windows在项目根显式ConfigureMedia，先备份日常库并追加0005，再配置两个媒体环境变量后启动；`check-media.cmd`默认只读，`-Record`记录容量，`-Deep -Details`核验并定位附件。完整命令见项目根`MEDIA_STORAGE.md`、`LOCAL_START.md`及`DATABASE_BACKUP.md`。

Linux核心CLI为`python -m app.media_storage --initialize`及`python -m app.media_diagnostics`，仅使用项目代码和既有环境，不读取全局skill目录。服务的两个ReadWritePaths及持久目录按文档配置。

发布沿用CheckOnly、Stage、MigrateReleaseId、ActivateReleaseId及暂存／备份／迁移／激活顺序。失败后核对current、数据库历史与两个包的card-schema-capability；标记不匹配不自动回退，不覆盖媒体，不执行down迁移。完整提交绑定、不可变执行工具绑定及线上版本探针属于原执行器后续建设范围，本次仅补充卡片兼容回退保护，不能由本地模拟声称整个发布体系已全面验证。

## Limits

- 未迁移或启用日常6171库，未改日常媒体配置；生产未连接、上传、迁移、激活或恢复。
- Linux仅模拟发布保护，不是systemd文件写权限／真实服务或生产版本探针实测；需要实际环境再验证。
- 此次测试媒体由沙盒账号创建，跨身份恢复仅为合成目录追加普通Windows账号读权限；正式初始化权限策略保持创建账号与SYSTEM，未扩大项目外或真实业务目录权限。
- 图片正文OCR、对象存储、永久清理、自动迁移、定时通知不在首版。服务端P95不替代浏览器端到端体验，缺测不当作0或通过。

测试结束后仅停止本次24568 API和核对目录后的6179自建实例；保留私有合成数据、包和恢复记录，没有递归清理或触碰日常服务。
