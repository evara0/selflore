# 资料卡、图片存储与排查

资料卡用于收录外部摘录或图片，原始材料与「我的说明」分开展示。收录不代表认同或核验为事实；未知作者、发布时间可留空。来源作者、发布／转载者和图片作者可分别填写。资料可被观点引用、加入合集、归档和恢复，不进入知识复习。

## 本机启用

先停止日常应用，按现有 `DATABASE_BACKUP.md` 备份开发库，再使用迁移角色运行追加迁移（0005），不修改历史SQL、不重建数据库。在项目根明确初始化两个目录：

```powershell
.\start-local.cmd -ConfigureMedia -MediaRoot G:\selflore-data\media -OpsRoot G:\selflore-data\media-ops
```

此命令为当前用户及SYSTEM设置新目录私有权限；已有已初始化目录只核对身份，不递归修改权限。随后在 `apps/api/.env` 添加以下非秘密设置，再执行 `start-local.cmd -CheckOnly` 和正常启动：

```dotenv
SELFLORE_MEDIA_ROOT=G:/selflore-data/media
SELFLORE_MEDIA_OPS_ROOT=G:/selflore-data/media-ops
```

媒体与运维目录必须互不嵌套，业务目录在代码／发布目录之外。普通启动和诊断不创建或修复目录。未配置媒体时保留文本卡片、摘录资料和健康检查；上传返回存储不可用。升级代码后的日常数据库须先追加迁移，不能直接沿用旧结构。

资料编辑器支持文件选择、拖拽，以及在任意编辑字段粘贴剪贴板图片；普通文字粘贴仍由对应字段处理。

首版每文件20 MiB、40百万像素、最长边20000像素，每卡10图；静态JPEG、PNG、WebP。可用 `SELFLORE_MEDIA_MAX_BYTES`、`SELFLORE_MEDIA_MAX_PIXELS`、`SELFLORE_MEDIA_MAX_EDGE` 调整前三项；界面显示实际值。原图字节保留，列表加载最大960像素WebP缩略图；原图可能包含EXIF，缩略图不保留EXIF。

## 按需排查

在Windows项目根运行：

```powershell
.\check-media.cmd
.\check-media.cmd -Json
.\check-media.cmd -Deep
.\check-media.cmd -Deep -Details
.\check-media.cmd -Record
.\check-media.cmd -Json -Output report-20261012.json
.\check-media.cmd -BandwidthMbps 10
```

默认只读并写stdout，不保存报告、不改库、不修改ACL、不删除或修复图片。`-Record`明确保存容量样本，`-Output`在受限运维目录保存新报告文件，不覆盖已有文件。`-Deep`读取原图和缩略图比对hash，大图片库可能耗时。首次检查或样本不足返回未知，不是健康的零值。
默认报告按问题代码聚合数量；`-Details`或Linux的`--details`明确显示有问题的附件ID，仍不显示正文、作者或图片内容。

Linux在已配置的API环境中运行核心CLI；预期端口必须与目标一致，不在命令行传密码：

```bash
python -m app.media_diagnostics --expected-port 6171 --json
python -m app.media_diagnostics --expected-port 6171 --deep --record
```

可通过 `--backup-root` 和 `--rehearsal-root` 指定已有记录目录，`--timeout`、`--max-files`限制扫描预算；各阈值参数见 `python -m app.media_diagnostics --help`。扫描受限时报告范围与未知，不标记全库通过。

| 指标 | 口径与默认提示 |
| --- | --- |
| 图片／卷容量 | 区分原图、缩略图、登记量、实际落盘、未引用ready与上传状态；磁盘为全卷占用，70%预警、80%严重 |
| 增长预测 | 显式容量样本至少跨度7天、最近30天；扣除max(卷容量10%,5 GiB)，不足90天预警、30天严重；零／负增长不可估计 |
| 完整性 | 默认存在与大小；Deep核对hash。被引用原图缺失／损坏严重，缺缩略图或未引用文件预警；不自动清理 |
| 请求表现 | 最近24小时有界遥测，上传／缩略图／原图分开；保留窗口完整且至少100样本才判断P95与失败率；缩略图服务端P95超过1秒、失败率超过1%预警 |
| 带宽 | 记录实际响应体字节，不含协议开销；显式提供带宽后才计算比例，连续三个完整5分钟桶超过50%预警 |
| 备份恢复 | 联合备份超过24小时、成功演练耗时超过2小时预警；数据库-only旧包不当作联合备份，无记录为未知 |

P95是服务端响应完成计时，不是浏览器端到端体验。遥测仅含时间、类别、状态、字节、耗时、传输结果和进程实例，不记录Cookie、URL、用户ID、附件ID或正文；锁保护六个最大5 MiB滚动文件，诊断只读。达到50 GiB仅提醒评估存储与备份，不强制迁移，也不创建定时任务。

退出码：0检查完成且正常；1预警或指标未知；2严重问题；3配置、身份、权限等导致检查未完成。优先保住原图和完成联合备份，再定位缩略图、路径、磁盘或带宽问题。单机容量不足可先扩盘，多实例共享或维护成本上升再考虑对象存储；迁移工具不在此版本。

## 备份、恢复与更新

固定 `backup-db.cmd` 在新结构上生成 `selflore-backup-v2`，同一数据库快照的dump、签名和ready附件清单对应原图／缩略图；包含回收站、归档、未引用ready，不包含上传中及未知孤立文件。文件缺失或损坏不会生成完整成功清单。

`backup-db.cmd -Rehearse` 使用新建的密码保护6179实例及独立媒体目录，核对库结构／数据／关系和文件hash，并通过临时本人会话读取恢复后的图片；探测会话随后清除。日常6171和媒体目录不作为演练目标。旧无附件v1备份仍可恢复，新库缺附件不能伪装成v1完整包。具体命令见 `DATABASE_BACKUP.md`。

删除卡片及移除图片仅改变关系，已完成原图保留；首版无永久附件清理。媒体不进入Git或发布包，程序更新不移动目录。已有资料后不能自动回退到只认识两类卡片的旧应用；保留新数据，使用兼容版本修复或暂时停用上传。
新包携带`app/card-schema-capability`标记。探针失败时，发布脚本仅在前一版本声明相同能力时自动回退；标记缺失或不匹配则保持新版本指针、返回失败并要求管理员处理，不执行反向迁移。恢复之前核对`current`指针、实际数据库迁移历史和两个版本的能力标记；不能手工给旧程序补标记以绕过检查。

## Linux发布准备（尚未生产演练）

管理员预建 `/srv/selflore/shared/media` 和 `/srv/selflore/shared/media-ops`，所属selflore且权限0700；显式初始化环境标识后配置对应环境变量。systemd保留ProtectSystem=strict，只对这两个路径设置ReadWritePaths；自定义路径需同步修改服务授权并核对权限。缺目录的可选路径不会阻止旧文本服务启动，但不会令图片上传可用。
在Linux的 `/srv/selflore/current/apps/api` 目录，以selflore服务账号使用现有虚拟环境执行：

```bash
python -m app.media_storage --initialize --environment prod --media-root /srv/selflore/shared/media --ops-root /srv/selflore/shared/media-ops
```

初始化不访问数据库，不自动写运行环境文件；已有非空且标识不符的目录会被拒绝。此CLI逻辑在Windows临时目录验证，Linux systemd写权限仍待实机验证。

生产发布前暂停应用写入，备份生产数据库并按相同状态的ready清单打包原图／缩略图、核对hash，形成受限联合备份后再恢复服务。备份失败不得激活新版；不得拿本机固定开发库工具直接连接生产。保留暂存→联合备份→指定版本迁移→激活流程，真正的生产备份恢复需另行授权并演练；本次仅本机隔离验证。同盘备份不提供异地容灾，应另存到受控介质或异地存储。
