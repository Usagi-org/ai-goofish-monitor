## ADDED Requirements

### Requirement: Web 应用 SHALL 支持 PWA 安装
系统 SHALL 配置 PWA manifest 和 Service Worker，支持用户将应用安装为桌面应用。

#### Scenario: PWA manifest 配置
- **WHEN** 浏览器访问应用时
- **THEN** 系统返回 manifest.json，包含应用名称、图标、启动方式（standalone）、主题色

#### Scenario: Service Worker 注册
- **WHEN** 应用加载时
- **THEN** 系统注册 Service Worker，支持离线访问基本页面

#### Scenario: 安装提示
- **WHEN** 浏览器支持 PWA 且用户未安装时
- **THEN** 前端显示「安装到桌面」提示按钮

### Requirement: 独立窗口运行
系统 SHALL 支持以独立窗口（无边框浏览器窗口）打开应用。

#### Scenario: standalone 启动模式
- **WHEN** 用户从桌面快捷方式启动应用时
- **THEN** 应用以独立窗口打开，无浏览器地址栏和工具栏

#### Scenario: 窗口大小记忆
- **WHEN** 用户关闭应用窗口时
- **THEN** 系统记录窗口大小和位置，下次启动时恢复
