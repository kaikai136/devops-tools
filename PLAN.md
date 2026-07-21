# SSH 网关终端模块设计方案

## Summary

设计一个 KoKo 风格的完整 SSH 网关模块，支持外部 SSH/SFTP/SCP 客户端连接平台并代理到受管 Linux/Unix 主机。第一版包含 SSH Shell、SFTP、SCP、交互式资产菜单、直连别名、平台密码 + TOTP 认证、会话录像、命令审计和文件操作审计。

默认网关端口为 `2222`，但必须支持部署时修改。

## Key Changes

- 新增 `backend/web_terminal/gateway/` 子模块：
  - SSHD 接入层：使用 `asyncssh` 监听配置端口。
  - 认证层：校验 Django 用户密码、账号状态、`hosts.terminal` 权限；启用 2FA 的用户通过 keyboard-interactive 输入 TOTP。
  - 资产选择层：支持 `ssh 用户名@网关` 菜单选择，也支持 `ssh 用户名#主机ID@网关` 直连。
  - Shell 代理层：桥接本地 SSH PTY 与目标 Paramiko shell channel。
  - SFTP/SCP 层：菜单模式展示虚拟资产目录；直连模式直接映射目标主机路径。
  - 审计层：复用现有 `TerminalSession`、asciicast 录像和命令风险识别，并新增文件传输审计。

- 配置与部署：
  - 新增环境变量：`SSH_GATEWAY_ENABLED=1`、`SSH_GATEWAY_BIND_HOST=0.0.0.0`、`SSH_GATEWAY_PORT=2222`、`SSH_GATEWAY_PUBLIC_HOST`、`SSH_GATEWAY_PUBLIC_PORT=2222`、`SSH_GATEWAY_HOST_KEY_PATH=/app/data/ssh-gateway-host-key`。
  - `docker-compose.yml` 使用 `${SSH_GATEWAY_PUBLIC_PORT:-2222}:${SSH_GATEWAY_PORT:-2222}`，部署时可在 `.env` 或私有 env 文件中改端口。
  - 示例：`SSH_GATEWAY_PUBLIC_PORT=22022 SSH_GATEWAY_PORT=2222` 表示宿主机暴露 `22022`，容器内仍监听 `2222`。
  - 示例：`SSH_GATEWAY_PUBLIC_PORT=22022 SSH_GATEWAY_PORT=22022` 表示宿主机和容器都使用 `22022`。
  - 新增 management command：`python manage.py run_ssh_gateway`。
  - `Dockerfile` 增加 `EXPOSE 2222`，但实际端口以环境变量为准。

- 数据模型扩展：
  - `TerminalSession` 增加 `user`、`username`、`entrypoint`、`client_ip`、`remote_username`、`direct_mode`。
  - 新增 `TerminalFileAudit`，记录 SFTP/SCP 的操作、路径、大小、状态、错误、用户和主机。
  - 第一版目标主机账号使用 `ManagedHost.login_user/login_password/private_key`，不新增多账号授权模型。

- API：
  - 新增 `GET /api/web-terminal/ssh-gateway/connection-info/?host=<id>`，返回 SSH/SFTP/SCP 示例命令，并使用 `SSH_GATEWAY_PUBLIC_HOST` 和 `SSH_GATEWAY_PUBLIC_PORT`。
  - 新增 `GET /api/web-terminal/file-audits/`，复用 `hosts.session_audit` 权限。

## Test Plan

- 后端测试：
  - 端口配置读取：默认 `2222`、自定义监听端口、自定义公开端口、Compose 示例命令生成。
  - 认证：密码错误、禁用用户、无权限、TOTP 成功/失败。
  - 资产解析：菜单模式、直连模式、非法主机 ID、Windows/RDP 主机拒绝。
  - Shell 代理：输入、输出、resize、连接失败、会话关闭和录像写入。
  - SFTP/SCP：虚拟目录、直连路径、上传、下载、删除、重命名和审计。
  - 审计 API：权限、筛选、返回字段。

- 集成测试：
  - 用 `asyncssh.connect()` 连接测试网关，验证 shell、SFTP list、SCP put/get。
  - 使用 fake Paramiko target client，避免依赖真实远程主机。
  - 跑现有 `web_terminal`、`accounts`、`host_management` 测试，确保 Web SSH/RDP 不回归。

## Assumptions

- 第一版不支持 Telnet、端口转发、命令阻断 ACL、多远程账号授权。
- 默认端口是 `2222`，部署时必须能通过环境变量修改公开端口和监听端口。
- 资产权限沿用当前项目能力：通过 `hosts.terminal` 控制是否可使用 SSH 网关。
- 参考 KoKo 的接入层、处理层、代理层、会话层、目标连接层分层，但实现形态适配 Django/Vue 项目。
