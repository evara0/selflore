---
title: "SelfLore · 项目维护卡"
project: "selflore"
updated: "2026-10-22"
status: "本次核对源码与文档；历史生产发布见验收记录，未重新部署"
environments:
  - "Windows 本地开发"
  - "Windows 隔离测试"
  - "Linux 生产（维护者本机发布工具）"
---

# SelfLore · 项目维护卡

**页面改动要构建，后端改动要重启，数据库升级先备份再独立迁移。**

SelfLore 是个人卡片笔记应用；功能与技术概览统一见[README](README.md)。

## 项目是什么

| 部分 | 位置与维护入口 |
| --- | --- |
| 前端 | `apps/web/src`；[前端命令与构建](apps/web/README.md) |
| 后端 | `apps/api/app`；[API 入口与配置](apps/api/README.md) |
| 数据／内容 | PostgreSQL `app` schema；图片位于代码目录外的私有目录 |
| 依赖 | 前端 pnpm 与 `pnpm-lock.yaml`，后端 uv 与 `uv.lock`；在各自应用目录执行命令 |

## 各环境怎么运行

| 环境 | 入口、端口与配置 | 操作说明 |
| --- | --- | --- |
| Windows 日常 | 仓库根 `start-local.cmd`；统一页面／API 24566，Vite热更新24567；开发库6171；`apps/api/.env`与独立凭据文件 | [固定启动、停止与排障](LOCAL_START.md) |
| 一次性测试 | `.cache/card-tests`；数据库6179、浏览器API24568；显式隔离DSN | [测试环境及清理边界](apps/api/WORKSPACE_TESTING.md) |
| Linux 生产 | `/srv/selflore/releases/<release-id>`、`current`；API回环24566，数据库6171；systemd与服务器独立环境配置 | 具体接入和发布命令仅在本机 `deploy/RELEASE_WORKFLOW.md`；[演示入口](https://selflore.evara.blog) |

固定启动的依赖同步、密码配置和停止／重启均见启动说明；通用手动运行及首位管理员见[认证配置](apps/api/AUTH_CONFIGURATION.md)。成功判断：页面可加载、健康检查正常，并用本人登录后的查询确认业务连接；生产需额外确认前后端版本及 readiness，不能只看健康200。

## 改什么，怎么生效

| 修改 | 位置 | 生效方式 |
| --- | --- | --- |
| 个人内容 | 页面编辑入口 | 保存到当前环境；不通过Git同步业务数据 |
| 页面／演示数据 | `apps/web/src` | Vite热更新；构建模式重建，生产重新发布 |
| 后端业务 | `apps/api/app` | 重启API；生产通过发布流程激活 |
| 数据结构 | 新编号SQL及迁移授权 | [升级流程](apps/api/CARD_MIGRATIONS.md)，启动不代替迁移 |
| 依赖／配置 | 应用清单、锁文件及运行环境 | 冻结同步依赖；配置改变后重启，生产Origin须匹配实际入口 |

## 程序更新到目标环境

本地：先按[备份与恢复](DATABASE_BACKUP.md)保留数据，需要结构升级时执行迁移，再重新运行固定启动或手动重启。图片配置与监控见[媒体维护](MEDIA_STORAGE.md)。

生产：使用维护者本机发布工具，依次完成指定提交检查与构建、同包暂存、管理员一致备份、本机备份副本核验、迁移、激活及版本／readiness核验。源码、迁移和构建产物随包，数据库、图片及运行凭据独立保留；不执行down SQL，只在已证明兼容时回退应用。自动发布工具不随公开仓库交付。

历史验收放在对应OpenSpec记录；[最近一次已记录的生产发布](openspec/changes/approve-memo-release-tools/validation.md)带有明确提交和证据，不代替每次更新的检查。

## 出问题先做什么

- 页面404：检查前端是否已构建，随后重启API；不要只凭健康接口判断页面可用。
- 登录／503：核对app角色、目标端口、迁移和Origin；参考[认证配置](apps/api/AUTH_CONFIGURATION.md)。
- 保存409：保留编辑内容，读取最新修订后合并，不反复覆盖。
- 迁移历史错误：恢复原SQL字节，勿修改历史账本；保留当前数据库和升级前备份。
- 日志：本地看运行终端；服务器看 `journalctl -u selflore-api.service`，用 `readlink -f /srv/selflore/current` 核对指向。
- 数据问题：卡片回收站可恢复；真正的数据库／媒体恢复按[备份说明](DATABASE_BACKUP.md)核对目标，日常和生产不能作为测试恢复目标。


## 统一标签升级

当前源码要求0007及 `reference-memo-tags-v1` 能力；尚未在日常／生产库执行。标签账号内共用，每卡可不选或多选，名称80字符、最多30项；内容类型与合集顺序保持原职责。操作前读[标签迁移与恢复手册](apps/api/TAG_MIGRATION.md)，先停写、备份和隔离恢复核验，再迁移／激活；不通过启动命令自动升级。

迁移后不要切回只认识旧分类的应用。保留旧ID映射、关系来源、快照和故障库，优先同能力兼容包或前向修复；恢复整库须明确备份截点及此后写入处理。当前worktree的本机工具副本和可审查补丁见本变更验收记录，未发布到主仓库或远端。
