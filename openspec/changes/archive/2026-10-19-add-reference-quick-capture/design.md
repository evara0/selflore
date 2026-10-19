## Context

CardForm管理来源状态，CardSources渲染字段；Owner依赖校验身份、Origin与CSRF。无来源解析器，httpx仅测试依赖；既有资料模型足够，不需迁移。

## Goals / Non-Goals

Goals：两种策略统一结果、安全抓取、失败可手填。Non-Goals：付费API、登录抓取、绕过反爬、远程图片下载、全文保存、AI分类、推断图片作者。

## Decisions

- POST /api/sources/resolve输入url、mode(auto/webpage)，返回category(webpage/x)、method(webpage/x_oembed)、status(success/partial/unavailable)、fallback_reason和fields（既有source_*字段），只预览不写库。
- 独立安全HTTP及平台解析模块；新增平台复用抓取边界和结果格式。普通网页是最终策略。
- X使用官方https://publish.x.com/oembed，传url、omit_script、dnt，只取author_name与首个推文p文本作短标题；不猜日期／转载者。支持x.com、twitter.com及www/mobile别名，只有帖子路径使用专用方式，失败回退网页。强制普通网页跳过专用策略。
- HTMLParser读取og:title、twitter:title、title以及author/citation_author、og:site_name、article:published_time/citation_publication_date；日期校验。站点名作为平台，不冒充作者或发布者，不信任canonical替换用户链接。
- 标准库http.client，无运行依赖变动。DNS结果全部必须公网，socket固定IP；HTTPS保留原hostname的SNI及证书检查。每跳校验，最多3次跳转，每次6秒、总约18秒网络预算，1MiB体积，拒绝压缩和不支持的类型。系统DNS解析可能超出读超时，不声称完全硬性超时。全局并发3，账号10次/分钟，进程内有界桶，多worker独立。
- 顶部来源链接、方式和获取按钮；用户显式点击才联网。侧栏链接保留同步。只在资料显示新模块，保留已有字段展开方式。
- 最新React状态只填空值；请求序号及链接／类型epoch拒绝旧响应，卸载忽略。请求中可修改和保存，失败不丢内容。纯文字显示，来源作者不写入图片作者。
- package.json只去重两项脚本，不调整命令。
- 获取期间记录各字段的手动触碰，主动清空也不被重新填入；响应头及正文读取使用剩余预算的连接中断定时器，防止持续小流量响应无限延长读取。

## Risks / Trade-offs

- X保护、删除、外站限流及网络限制 → 免费接口与网页双退路，实际联网单列结果，不承诺可获取所有链接。
- 登录墙和JS外壳 → 常见阻断标题过滤，缺失信息如实留空，不执行脚本。元信息可能不准，用户可编辑。
- URL可能含私人参数 → 明确获取才发送，不持久记录URL或缓存结果，不传会话。
- 系统DNS无法由读超时完整控制 → 并发边界，部署出口策略可补充；文档说明限制。

## Migration Plan

无数据库迁移；回滚代码恢复原表单，已有字段继续可读。本次不自动归档、提交或部署。

## Deferred Work

2026-10-19确认：可选出站代理为低优先级后续事项，本次不实现、不新增配置任务。用户反馈部署机器通常可直连，当前问题主要影响受限网络下的本机测试、个人使用及从GitHub克隆后的自部署。一次性7897 HTTP代理实测两种方式均返回200，说明该本机直连限制存在可用的网络替代路径；不据此宣称应用已支持代理或生产网络已实测。

当部署环境直连也持续失败、本机收录频繁受阻或多个自部署者反馈时，再建立独立变更。代理需配置服务端完整URL，默认关闭，不允许浏览器指定任意代理；代理端DNS及实际连接位置会影响现有固定公网IP机制，需要保留或重新建立等效的非公网地址、重定向和凭据边界。不能直接将现有安全读取替换成隐式遵从环境代理的客户端。现有spec保持直连安全约束，任务仍6/6完成，不把暂缓事项当作已实现能力。
