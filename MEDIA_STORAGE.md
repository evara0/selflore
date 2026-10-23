# 资料卡、图片存储与排查

本文负责私有图片目录、上传限制、只读诊断及部署前提。资料卡用途见[项目首页](README.md)，请求字段见[API说明](apps/api/WORKSPACE_API.md#资料卡与附件)；备份与恢复统一见[备份说明](DATABASE_BACKUP.md)。

## 本机启用

先备份开发库并按[迁移说明](apps/api/CARD_MIGRATIONS.md)应用完整链，再停止日常应用并准备媒体目录。以下命令在Windows仓库根运行，示例将存储放到仓库父目录的 `selflore-data`，不依赖维护者盘符：

```powershell
$repositoryPath = (Get-Location).Path
$storageBase = Join-Path (Split-Path -Parent $repositoryPath) 'selflore-data'
$mediaRoot = Join-Path $storageBase 'media'
$opsRoot = Join-Path $storageBase 'media-ops'
.\start-local.cmd -ConfigureMedia -MediaRoot $mediaRoot -OpsRoot $opsRoot
```

此命令为当前用户及SYSTEM设置新目录私有权限；已有已初始化目录只核对身份，不递归修改权限。将这两个变量的实际完整路径填入 `apps/api/.env`，路径建议使用正斜杠：

```powershell
# 输出实际路径后，分别作为 SELFLORE_MEDIA_ROOT 与 SELFLORE_MEDIA_OPS_ROOT 的值写入.env
$mediaRoot.Replace('\', '/')
$opsRoot.Replace('\', '/')
```

随后按[本地启动](LOCAL_START.md#日常启动和停止)执行检查和正常启动。只修改媒体路径变量不代表目录已初始化。

媒体与运维目录必须互不嵌套，业务目录在代码／发布目录之外。普通启动和诊断不创建或修复目录。未配置媒体时保留文本卡片、摘录资料和健康检查；上传返回存储不可用。升级代码后的日常数据库须先追加迁移，不能直接沿用旧结构。

资料编辑器支持文件选择、拖拽，以及在任意编辑字段粘贴剪贴板图片；普通文字粘贴仍由对应字段处理。

默认每文件20 MiB、40百万像素、最长边20000像素，每卡10图；静态JPEG、PNG、WebP。可用 `SELFLORE_MEDIA_MAX_BYTES`、`SELFLORE_MEDIA_MAX_PIXELS`、`SELFLORE_MEDIA_MAX_EDGE` 调整前三项；界面显示实际值。原图字节保留，列表加载最大960像素WebP缩略图；原图可能包含EXIF，缩略图不保留EXIF。

## 按需排查

在Windows项目根运行：

```powershell
.\check-media.cmd
.\check-media.cmd -Json
.\check-media.cmd -Deep
.\check-media.cmd -Deep -Details
.\check-media.cmd -Record
.\check-media.cmd -Json -Output report.json
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

命令、v1／v2格式、ready范围及隔离恢复统一见[备份与恢复](DATABASE_BACKUP.md)。数据库dump和媒体清单必须对应同一快照；仅有数据库文件不能算当前图片库的完整备份。

删除卡片及移除图片仅改变关系，已完成原图保留，当前没有永久附件清理。媒体不进入Git或发布包，程序更新不移动目录。应用能力与回退条件统一见[迁移兼容性](apps/api/CARD_MIGRATIONS.md#发布与回退)；不能给旧程序伪造标记绕过检查。

## Linux发布准备

管理员预建 `/srv/selflore/shared/media` 和 `/srv/selflore/shared/media-ops`，所属selflore且权限0700；显式初始化环境标识后配置对应环境变量。systemd保留ProtectSystem=strict，只对这两个路径设置ReadWritePaths；自定义路径需同步修改服务授权并核对权限。缺目录的可选路径不会阻止旧文本服务启动，但不会令图片上传可用。
在Linux的 `/srv/selflore/current/apps/api` 目录，以selflore服务账号使用现有虚拟环境执行：

```bash
python -m app.media_storage --initialize --environment prod --media-root /srv/selflore/shared/media --ops-root /srv/selflore/shared/media-ops
```

初始化不访问数据库，不自动写运行环境文件；已有非空且标识不符的目录会被拒绝。每个实际目标都需要核验服务账号、目录标识、权限和systemd写入范围，不能从本机初始化结果推断生产已就绪。

生产发布前通过维护者本机流程创建一致快照的联合备份及受保护收据，并完成本机副本核验；备份失败不得迁移或激活新版。具体接入与发布脚本不随公开仓库交付。生产恢复与灾难恢复需要单独的目标核对和演练，不能从成功备份推断已经验证；最近一次已有记录见[生产发布验收](openspec/changes/archive/2026-10-23-approve-tabular-release-tools/validation.md)。本次文档整理不执行这些操作。
