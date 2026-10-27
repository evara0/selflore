# 文档整理验收

- 时间：2026-10-27；执行者：Codex。
- 仓库：`E:/261027-selflore-idea/selflore`，分支 `main`，基线 `9551d7ee16d930376f6c1830223625f43b5796c9`。
- Git 前置检查：修正代理后重新 fetch origin 成功，`HEAD...@{u}` 为 `0 / 0`，main 跟踪 origin/main；初始工作区干净，无子模块及未完成 Git 操作，无需 pull。

## 整理结果

根目录 Markdown 从八份减少为三份：README.md、CONTRIBUTING.md、AGENTS.md。五份专项文档迁入 handbook/，保留文件名，README 目录树和导航表同步更新。六份应用说明的入链已指向新目录，五份手册的跨目录链接已重算。

SOURCE_CAPTURE.md 中两节“已知网络限制与代理支持计划”的内容完全相同，比较确认一致后仅删除一份。逐一将迁移前后的手册去掉链接目标进行比对：除该重复节外正文一致；所有 fenced 命令块逐字一致，命令的执行目录和操作边界保留。

未调整忽略规则；docs/、本机部署与备份资料、历史 OpenSpec 文档及原有修复 worktree 未修改。未保留根目录占位文件，旧路径的外部链接需使用新 handbook 路径；历史提交仍保留原文件。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 根目录 Markdown 列表及手册内容／命令块比较 | 三份根文档、五份手册；正文与命令保留检查通过 |
| `python scripts/check_docs.py` | 当前公开 Markdown 的 116 个本地链接／锚点，0 错误 |
| `python -m unittest discover -s scripts/tests -v` | 17 项通过，无失败或跳过 |
| `openspec validate organize-root-documentation --strict` | 通过 |
| `git diff --cached --check` | 通过 |
| Git 迁移识别 | 五份手册均识别为 rename，非无关删除 |

实施检查时为满足文档检查的跟踪要求，将变更加入索引，未自动提交或归档。用户随后明确要求验收、归档、提交和推送，交付前重新执行上述检查，结果均通过；远端刷新后 main 与 origin/main 仍为 0 / 0。按授权归档本变更并同步 project-overview 主规范，随后提交推送；Git 提交及远端状态由交付结果确认，不等同生产发布。

## 覆盖边界

纯 Markdown 组织与引用变更，无源码、配置、运行命令或应用展示变化，前端构建、数据库及浏览器视觉审查不适用；没有生成或查看应用截图。外站链接可用性、历史 OpenSpec 内的旧路径和被忽略的本机文档不属于当前公开链接检查范围。
