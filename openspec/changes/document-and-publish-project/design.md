## Context

当前前后端基线已可构建。

## Goals / Non-Goals

**Goals:** 提供简明技术说明并发布当前工作树。

**Non-Goals:** 不创建远程仓库、不改写远程历史。

## Decisions

采用根目录 `PROJECT_OVERVIEW.md`，仅显式暂存可跟踪项目文件后推送。

## Risks / Trade-offs

- [远程已有历史] → 推送前检查，拒绝非快进覆盖。
