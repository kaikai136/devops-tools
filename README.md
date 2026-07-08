# 运维工具平台

这是一个基于 Django REST API + Vue 3 + Vite 重构的 Web 运维工具平台，提供主机资产管理、Web 终端、网络探测、安全工具、审计日志和系统管理能力。项目支持本地开发运行，也支持通过 Docker Compose 一键构建部署。

## 功能概览

### 仪表盘

- 系统总览、资产统计、用户与安全状态概览。
- 网络与主机数据聚合展示。
- 图表化展示关键指标，便于快速了解平台运行情况。

### 主机与终端管理

- 主机资产管理：维护主机名称、IP、端口、系统类型、登录账号、分组和备注信息。
- 主机分组：支持默认分组、自定义分组和分组视图。
- 主机验证：可对主机连通性、登录信息和系统信息进行探测验证。
- 批量导入导出：支持主机清单备份、导入、导出和字段选择。
- Web SSH 终端：通过浏览器连接 Linux/Unix 主机，支持终端字号、搜索、复制、快捷命令等常用操作。
- Web RDP 终端：通过 guacd 支持 Windows/RDP 连接。
- 远程文件工具：支持浏览远程目录、创建文件/目录、上传、下载、重命名、删除、权限调整等操作。
- 资源监控：在终端侧查看远程主机基础资源信息。
- 多主机执行：面向已选主机执行批量命令。
- 会话审计：记录 SSH/RDP 会话、命令风险等级、操作时间和来源。
- 操作录像：支持终端会话录像回放，RDP 录像文件可按保留周期清理。

### 网络工具

- IP 探活：对局域网 1-254 地址段进行在线探测。
- Ping 探测：检测目标主机连通性、延迟和结果趋势。
- 端口扫描：扫描常用端口或指定端口，识别开放服务。
- 机器探测：组合 Ping、端口和基础网络信息，快速判断主机可达性。
- IPv4 子网划分：支持 CIDR 计算、子网拆分、地址范围和可用主机数计算。

### 安全工具

- 双因子认证：管理 TOTP 动态口令条目，支持二维码识别、导入和导出。
- 密码生成器：生成强密码，支持长度、字符类型和强度配置。
- 密码记录：保存密码条目，支持导入、导出和历史管理。
- 登录保护：支持用户双因子登录、会话锁定和个人安全设置。

### 系统管理

- 用户管理：创建、禁用、删除用户，重置密码和重置双因子认证。
- 角色管理：配置角色权限与授权范围，控制页面和操作级权限。
- 账号管理：管理平台账号状态、权限和基本资料。
- 登录日志：查看登录时间、来源 IP、登录状态和失败原因。
- 操作日志：记录用户在平台内的关键操作，便于审计追踪。
- 个人中心：维护头像、资料、密码和登录保护设置。
- 系统设置：配置应用名称、Logo、图标、水印、页脚、主题偏好等基础参数。
- 水印与品牌：支持工作区水印和品牌展示配置。

## 技术架构

- 后端：Django、Django REST Framework、Django Channels、Daphne。
- 前端：Vue 3、Vite、TypeScript、ECharts、xterm.js、Guacamole Common JS。
- 终端能力：SSH 连接依赖 Paramiko，RDP 连接依赖 guacamole/guacd。
- 静态资源：前端构建后由 Django + WhiteNoise 提供。
- 数据存储：默认使用 SQLite，数据文件通过 Docker volume/挂载目录持久化。
- 部署方式：Docker 多阶段构建，Docker Compose 编排 app 与 guacd 服务。

## 目录结构

```text
django-vue/
├── backend/                 # Django API、WebSocket、模型和业务逻辑
│   ├── accounts/            # 登录、用户资料、权限认证、会话锁定
│   ├── authenticators/      # TOTP 动态口令管理
│   ├── host_management/     # 主机资产、分组、探测、导入导出
│   ├── network_tools/       # IP 探活、Ping、端口扫描、子网计算
│   ├── operations/          # API 路由聚合和健康检查
│   ├── passwords/           # 密码生成与密码记录
│   ├── system_management/   # 系统设置、日志、仪表盘
│   ├── web_terminal/        # Web SSH/RDP 终端、文件工具、会话审计
│   └── ops_tool/            # Django 项目配置、ASGI/WSGI、前端入口
├── frontend/                # Vue 3 前端应用
│   ├── src/components/      # 页面与通用组件
│   ├── src/composables/     # 页面状态和功能逻辑
│   ├── src/services/        # API 请求封装
│   └── src/styles/          # 全局样式和功能模块样式
├── docker/                  # 容器启动脚本
├── scripts/                 # 本地/远程部署脚本
├── Dockerfile               # 前后端多阶段构建镜像
└── docker-compose.yml       # app + guacd 服务编排
```

## 本地开发

### 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

后端默认地址：

```text
http://127.0.0.1:8001
```

健康检查：

```bash
curl http://127.0.0.1:8001/api/health/
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:5173
```

前端生产构建：

```bash
cd frontend
npm run build
```

## Docker 部署

### 前置条件

- Docker
- Docker Compose v2，或兼容的 `docker-compose`
- 服务器开放应用端口，默认容器内端口为 `8001`

### 环境变量

首次部署前可在项目根目录创建 `.env`：

```env
APP_PORT=8001
DJANGO_SECRET_KEY=change-me-to-a-long-random-secret
DJANGO_ALLOWED_HOSTS=172.16.0.99,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=http://172.16.0.99:8001,http://localhost:8001,http://127.0.0.1:8001
DJANGO_CORS_ALLOW_ALL_ORIGINS=0
RDP_RECORDING_RETENTION_DAYS=30
RDP_RECORDING_DEFAULT_ENABLED=0
```

常用变量说明：

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `APP_PORT` | 宿主机暴露端口 | `8001` |
| `DJANGO_SECRET_KEY` | Django 密钥，生产环境必须设置 | 无 |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的域名/IP | `172.16.0.99,localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF 信任来源 | 按部署地址配置 |
| `DJANGO_DB_PATH` | 容器内 SQLite 路径 | `/app/data/db.sqlite3` |
| `DJANGO_MEDIA_ROOT` | 容器内媒体文件路径 | `/app/media` |
| `GUACD_HOST` | guacd 服务地址 | `guacd` |
| `GUACD_PORT` | guacd 服务端口 | `4822` |
| `RDP_RECORDING_RETENTION_DAYS` | RDP 录像保留天数 | `30` |
| `RDP_RECORDING_DEFAULT_ENABLED` | 是否默认开启 RDP 录像 | `0` |

### 启动服务

```bash
docker compose up -d --build
docker compose ps
```

或使用项目脚本自动生成 `.env` 并启动：

```bash
bash scripts/compose-up.sh
```

部署完成后访问：

```text
http://服务器IP:APP_PORT
```

健康检查：

```bash
curl http://127.0.0.1:8001/api/health/
```

如果 `.env` 中将 `APP_PORT` 设置为其他端口，请使用对应端口检查，例如：

```bash
curl http://127.0.0.1:8003/api/health/
```

### 数据持久化

Docker Compose 会挂载以下持久化目录：

- `./data:/app/data`：SQLite 数据库。
- `./media:/app/media`：上传文件、头像、媒体资源。
- `rdp_recordings:/app/rdp_recordings`：RDP 录像数据卷。

升级或重建镜像不会删除以上数据。删除目录或 volume 前请先备份。

## 远程部署

项目提供 `scripts/deploy-remote.sh` 用于在远程服务器拉取仓库并通过 Docker Compose 启动。

### 默认参数

| 参数 | 默认值 |
| --- | --- |
| `DEPLOY_HOST` | `172.16.0.99` |
| `DEPLOY_USER` | `root` |
| `DEPLOY_ROOT` | `/opt` |
| `APP_NAME` | `devops-tools` |
| `REPO_URL` | `https://github.com/kaikai136/devops-tools.git` |
| `BRANCH` | `main` |
| `APP_PORT` | `8001` |

### 部署指定版本

远程部署脚本默认按分支部署。如果要部署 `v2.0.0`，建议明确传入 tag 名称：

```bash
DEPLOY_HOST=172.16.0.99 \
DEPLOY_USER=root \
DEPLOY_ROOT=/opt \
APP_NAME=devops-tools \
REPO_URL=https://github.com/kaikai136/devops-tools.git \
BRANCH=v2.0.0 \
APP_PORT=8001 \
bash scripts/deploy-remote.sh
```

如果服务器已有 `.env`，脚本不会覆盖已有配置；实际访问端口以远程 `.env` 中的 `APP_PORT` 为准。

### 手动远程部署流程

也可以直接登录服务器执行：

```bash
cd /opt
git clone https://github.com/kaikai136/devops-tools.git devops-tools
cd /opt/devops-tools
git fetch --tags --force origin
git checkout --detach refs/tags/v2.0.0
mkdir -p data media
docker compose up -d --build
docker compose ps
```

首次部署请先按上文“环境变量”章节创建 `.env`，已存在 `.env` 时不要覆盖生产配置。

### 部署验证

```bash
cd /opt/devops-tools
git describe --tags --always --dirty
git rev-parse HEAD
docker compose ps
APP_PORT="$(awk -F= '/^APP_PORT=/{print $2; exit}' .env 2>/dev/null || true)"
APP_PORT="${APP_PORT:-8001}"
curl http://127.0.0.1:${APP_PORT}/api/health/
```

预期健康检查返回：

```json
{"status":"ok"}
```

## 常用运维命令

查看服务状态：

```bash
docker compose ps
```

查看应用日志：

```bash
docker compose logs -f app
```

查看 guacd 日志：

```bash
docker compose logs -f guacd
```

重启服务：

```bash
docker compose restart
```

重建并滚动启动：

```bash
docker compose up -d --build
```

执行数据库迁移：

```bash
docker compose exec app python manage.py migrate
```

清理过期 RDP 录像：

```bash
docker compose exec app python manage.py cleanup_rdp_recordings
```

进入 Django shell：

```bash
docker compose exec app python manage.py shell
```

## 默认访问入口

- Web 应用：`http://服务器IP:APP_PORT`
- 管理后台：`http://服务器IP:APP_PORT/admin/`
- 健康检查：`http://服务器IP:APP_PORT/api/health/`
- 终端页面：`http://服务器IP:APP_PORT/terminal.html`

## 注意事项

- 生产环境必须设置强随机 `DJANGO_SECRET_KEY`。
- `DJANGO_ALLOWED_HOSTS` 和 `DJANGO_CSRF_TRUSTED_ORIGINS` 需要按实际域名/IP/端口配置。
- Web RDP 功能依赖 `guacamole/guacd:1.5.5` 容器，请确认 guacd 服务正常启动。
- SSH 终端依赖目标主机网络可达，并需要正确的登录账号、密码或密钥配置。
- SQLite 适合轻量部署；如果用户量、审计数据或并发规模较大，建议评估迁移到独立数据库。
- 升级前建议备份 `data/`、`media/` 和 RDP 录像 volume。
