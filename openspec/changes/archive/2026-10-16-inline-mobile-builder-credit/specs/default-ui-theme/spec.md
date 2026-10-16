## MODIFIED Requirements

### Requirement: 构建者外链与交互动效
系统 SHALL 显示署名 Produced by Evara，用 GitHub 图标和小写 b 字母博客图标提供构建者入口，分别链接到 https://github.com/evara0/selflore 和 https://evara.blog/。桌面品牌右侧及页脚和手机品牌右侧 SHALL 提供可见入口，手机品牌与整个构建者组 MUST 排列在同一行，组内署名 MUST 位于两个图标下方，外链 SHALL 在新标签页打开并阻止访问原窗口。入口 SHALL 有明确可访问名称、可见键盘焦点和足够触控区域；悬停、焦点与按压 SHALL 提供短暂动效，减少动态效果偏好下 MUST 禁用动效。入口 MUST 不影响导航、认证及 320 至 1440 像素宽度布局。

#### Scenario: 找到并打开构建者链接
- **WHEN** 游客或已登录用户在桌面或手机查找构建者信息
- **THEN** 两个图标 SHALL 可见可达，指向指定地址并在受保护的新标签页打开

#### Scenario: 键盘与动画偏好
- **WHEN** 用户用键盘聚焦入口或启用减少动态效果偏好
- **THEN** 焦点 SHALL 清晰，启用该偏好时入口不执行动画、过渡或移动变换
