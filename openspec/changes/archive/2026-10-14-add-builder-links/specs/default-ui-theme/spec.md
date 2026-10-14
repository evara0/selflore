## MODIFIED Requirements

### Requirement: 简洁的品牌表达
界面 SHALL 保留 SelfLore 名称并以“个人卡片笔记”说明用途。主页面和编辑页 MUST 不展示反复的成长、痕迹或连接口号和装饰性英文眉题；页脚 SHALL 显示名称及克制的构建者外链入口，不增加宣传口号。用户未填写简介时 MUST 不替用户展示品牌宣言。卡片编号、纸墨框线和必要操作说明 SHALL 保留。

#### Scenario: 浏览主要页面
- **WHEN** 用户访问知识、观点、合集、我的或编辑页
- **THEN** 页面 SHALL 展示明确标题及操作，不出现重复宣传块和默认个人宣言

### Requirement: 一致的品牌符号
页头和浏览器图标 SHALL 使用相同的紫色八向发散线条标志。观点导航 SHALL 使用笔形图标，关联入口 SHALL 继续使用链环。图标 MUST 不改变可访问名称或导航目标。

#### Scenario: 桌面与手机导航
- **WHEN** 用户在桌面或手机查看品牌和导航
- **THEN** 标志 SHALL 清晰一致，观点与关联图标用途区分，四页及新建入口保持可达

## ADDED Requirements

### Requirement: 构建者外链与交互动效
系统 SHALL 显示署名 Produced by Evara，用 GitHub 图标和小写 b 字母博客图标提供构建者入口，分别链接到 https://github.com/evara0/selflore 和 https://evara.blog/。桌面品牌右侧及页脚和手机品牌下方独立一行 SHALL 提供可见入口，手机署名 MUST 位于两个图标下方，外链 SHALL 在新标签页打开并阻止访问原窗口。入口 SHALL 有明确可访问名称、可见键盘焦点和足够触控区域；悬停、焦点与按压 SHALL 提供短暂动效，减少动态效果偏好下 MUST 禁用动效。入口 MUST 不影响导航、认证及 320 至 1440 像素宽度布局。

#### Scenario: 找到并打开构建者链接
- **WHEN** 游客或已登录用户在桌面或手机查找构建者信息
- **THEN** 两个图标 SHALL 可见可达，指向指定地址并在受保护的新标签页打开

#### Scenario: 键盘与动画偏好
- **WHEN** 用户用键盘聚焦入口或启用减少动态效果偏好
- **THEN** 焦点 SHALL 清晰，启用该偏好时入口不执行动画、过渡或移动变换

### Requirement: 品牌与账号入口分区
构建者链接 SHALL 归于品牌区域，MUST 不占用账号区域。游客 MUST 不显示重复的页头登录按钮，页面演示横幅 SHALL 保留登录／注册入口，写入操作 SHALL 继续提示认证。已登录用户 SHALL 保留页头头像或用户名及账号设置入口。

#### Scenario: 游客与已登录账号
- **WHEN** 用户在游客和登录状态查看页头
- **THEN** 游客 SHALL 从横幅或认证门禁登录，已登录用户 SHALL 从独立账号入口进入设置，构建者外链与账号入口不重叠
