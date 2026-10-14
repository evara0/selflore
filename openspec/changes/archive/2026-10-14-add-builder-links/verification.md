# 构建者与品牌区域验收

日期：2026-10-14。任务 3/3 完成，以下记录最终方案。

- 桌面页头左侧品牌与 Produced by Evara 双图标组以细竖线分隔；右侧保留新建及登录后的账号入口，页脚右侧仍保留构建者组。
- 手机第一行品牌与登录后的账号，第二行在品牌下方显示 GitHub 和小写 b 图标，署名在图标下方。
- 页头和 favicon 共用紫色八向发散线条 SVG，恢复原来标志形态。
- 游客不显示页头重复登录，保留演示横幅登录／注册与写入认证门禁；已登录账号仍从头像／用户名进入设置。
- 外链精确为 https://github.com/evara0/selflore 和 https://evara.blog/，新标签页带 noopener noreferrer。链接有独立可访问名称、提示、44×44 点击区域及键盘焦点。
- 保留悬停／焦点短暂摆动和触控按压反馈，减少动态效果时禁用动画、过渡和变换。

## Validation

- 前端 57 项单元测试通过，lint --deny-warnings、TypeScript 和 Vite build 通过。
- 最终静态构建 Playwright：guest、mobile-create、registration、theme，共 9 项通过（56.8 秒）；认证校验及隔离断言保持。
- 320、390、736、1024、1440 宽度：无横向溢出，手机文字位于图标下方；游客无 account-trigger，构建者归于 brand-area。
- 登录夹具的长用户名在五档宽度下账号与品牌区域不重叠；已登录设置入口仍由现有单元及移动回归覆盖。
- 精确链接、新标签页 window.opener=null、键盘 Tab 与焦点、减少动态效果均通过。外站请求拦截，仅验证导航目的地；未访问外站。
- 本轮所有浏览器业务 API 使用显式夹具，无生产或日常数据库操作。既有测试登录动作迁移到横幅入口，并等待游客检测完成；未放宽校验。
- 已查看 [桌面页头](../../../../docs/design/add-builder-links/desktop-header.png)、[手机](../../../../docs/design/add-builder-links/mobile.png)；页脚截图位于同目录。
- OpenSpec 严格校验及 git diff --check 通过。

本变更尚未归档、Git 提交或部署。
