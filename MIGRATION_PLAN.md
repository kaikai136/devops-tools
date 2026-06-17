# Django + Vue3 重构迁移计划

## 目标

将现有 Tauri + React + Rust 桌面应用迁移为 Django REST API + Vue 3 Web 应用，同时保留原有运维工具功能。

## 当前重构范围

- 后端：`django-vue/backend`
- 前端：`django-vue/frontend`
- 原 Tauri 实现继续保留，作为功能对照和桌面版本发布线。

## 已完成

- Django 项目骨架
- Vue 3 项目骨架
- IP 探活 API 与页面
- 端口扫描 API 与页面
- 快速端口测试 API 与页面
- Ping API 与页面
- IPv4 子网计算 API 与页面
- 密码生成器 API 与页面
- TOTP 双因子认证 API 与页面
- 密码历史、Ping 历史、TOTP 条目数据库模型

## 与原桌面版差异

- 扫描进度目前为一次请求返回完整结果，尚未接入 WebSocket 实时推送。
- Ping 使用系统 `ping` 命令，行为会受操作系统权限和网络策略影响。
- TOTP 二维码图片识别尚未迁移，当前支持手动录入和分享二维码生成。
- 文件导出能力后续可在前端通过 Blob 下载或由 Django 提供导出接口补齐。

## 下一步

1. 引入 WebSocket 或 Server-Sent Events，恢复扫描实时进度。
2. 补齐 Ping 图表、历史导出、密码导出和认证条目 JSON 备份。
3. 迁移二维码图片识别导入能力。
4. 增加登录认证和多用户数据隔离。
5. 增加后端单元测试与前端组件测试。
