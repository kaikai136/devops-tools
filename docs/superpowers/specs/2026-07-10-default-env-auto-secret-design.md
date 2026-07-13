# 默认环境配置与首次启动密钥设计

日期：2026-07-10

## 目标

让使用者拉取仓库后，无需手工创建 `.env` 或预先生成 Django 密钥，即可直接运行：

```bash
docker compose up -d --build
```

同时保证每套部署使用独立密钥，容器重启和镜像重建后密钥保持不变，并允许生产环境显式覆盖全部默认配置。

## 当前问题

- 根目录 `.env` 被 `.gitignore` 排除，仓库没有可直接使用的 Compose 环境文件。
- `docker-compose.yml` 使用必填表达式要求 `DJANGO_SECRET_KEY`，未创建 `.env` 时 Compose 在构建或启动前即失败。
- `scripts/compose-up.sh` 和 `scripts/deploy-remote.sh` 能生成 `.env`，但直接执行 `docker compose up -d --build` 仍不可用。
- 若在仓库默认 `.env` 中提交固定密钥，所有未修改配置的部署会共享同一密钥，不符合安全要求。

## 选定方案

采用容器入口脚本首次生成并持久化 Django 密钥：

1. 仓库跟踪一个不含真实秘密的根目录 `.env`。
2. 默认 `.env` 将 `DJANGO_SECRET_KEY` 留空。
3. Compose 将该变量传入容器，但不再通过必填表达式阻止启动。
4. 容器入口脚本按优先级处理密钥：
   - 非空的 `DJANGO_SECRET_KEY` 环境变量；
   - 已存在的 `/app/data/django-secret-key`；
   - 首次启动时安全生成的新密钥。
5. 自动生成的密钥写入已挂载的 `/app/data`，因此容器重启和镜像重建不会改变密钥。

## 默认 `.env`

仓库根目录新增并跟踪 `.env`，提供开箱即用的默认配置，包括：

- `APP_PORT=8001`
- 默认镜像名和容器名
- guacd 容器名
- `DJANGO_SECRET_KEY=`（空值表示自动生成）
- `DJANGO_ALLOWED_HOSTS=*`
- 空的 `DJANGO_CSRF_TRUSTED_ORIGINS`
- 关闭跨域全放行
- RDP 录像保留时间和默认开关

默认配置定位为本地、测试和受控内网环境的开箱即用配置。生产环境应将允许主机、CSRF 来源和其他部署参数改为实际域名或 IP。

`.gitignore` 将只为仓库根目录默认 `.env` 添加例外，同时继续忽略 `.env.local`、`.env.production` 等私有环境文件。

## 密钥生命周期

入口脚本将在执行数据库迁移之前处理密钥：

1. 使用 `umask 077`，确保新文件默认仅拥有者可读写。
2. 如果 `DJANGO_SECRET_KEY` 非空，直接导出并使用，不写入日志。
3. 如果环境变量为空但 `/app/data/django-secret-key` 存在，读取并导出。
4. 如果两者都不存在，使用容器内 Python 的 `secrets.token_urlsafe()` 生成足够长度的随机密钥，原子写入持久化文件，并设置严格权限。
5. 日志只说明密钥来源，不输出密钥内容。

显式环境变量始终具有最高优先级，以支持 Docker Secret、CI/CD 变量或生产环境私有 `.env`。

## Compose 与脚本行为

### Docker Compose

- 移除 `DJANGO_SECRET_KEY` 的必填错误表达式。
- 将空值正常传递给入口脚本。
- 保留 `./data:/app/data`，作为数据库和自动密钥的持久化位置。
- 默认 `.env` 可直接驱动镜像构建和服务启动。

### `scripts/compose-up.sh`

- 不再负责生成 `.env` 或密钥。
- 只创建必要持久化目录，然后运行 Compose 构建和启动。
- 继续作为方便入口，但不再是首次部署的必要步骤。

### `scripts/deploy-remote.sh`

- 新部署直接使用仓库自带默认 `.env`。
- 已有部署若有自定义 `.env`，更新仓库时必须保留该文件内容。
- 脚本在切换或更新代码前临时备份现有 `.env`，完成代码更新后恢复，避免被仓库版本覆盖。
- 脚本不生成或显示 Django 密钥；密钥由容器入口统一管理。

## 文档调整

README 的 Docker 部署章节将包括：

1. 克隆后直接构建启动的最短命令。
2. 仓库默认 `.env` 的定位和安全边界。
3. 环境变量完整说明，包括默认值、用途和生产建议。
4. 密钥优先级和 `/app/data/django-secret-key` 的持久化行为。
5. 使用私有环境文件的推荐命令，例如：

   ```bash
   cp .env .env.production
   docker compose --env-file .env.production up -d --build
   ```

6. 域名/IP、HTTPS、CSRF 配置示例。
7. 已有部署升级时保留私有 `.env` 和 `data` 目录的注意事项。
8. 健康检查和常用维护命令。

## 安全约束

- 仓库不得提交真实生产密钥、令牌、密码或证书。
- 自动密钥不得输出到日志。
- 密钥文件应使用严格权限并保存在持久化目录。
- 删除 `./data` 会同时删除 SQLite 数据库和自动生成的 Django 密钥，文档必须明确要求先备份。
- 默认 `DJANGO_ALLOWED_HOSTS=*` 仅为开箱即用；生产环境必须收紧。
- 默认不启用跨域全放行。

## 兼容性

- 已显式配置 `DJANGO_SECRET_KEY` 的部署行为保持不变。
- 已有 `./data/django-secret-key` 的部署会持续复用同一密钥。
- 已有私有 `.env` 的远程部署通过脚本更新时不会被仓库默认文件覆盖。
- Docker Compose v2 为主要支持目标，现有远程脚本继续兼容 `docker-compose`。

## 验证标准

实施后必须验证：

1. 不手工创建 `.env`，仓库默认文件存在且 Compose 配置可成功解析。
2. `DJANGO_SECRET_KEY` 留空时，首次启动生成 `/app/data/django-secret-key`。
3. 密钥文件非空，且应用日志不包含密钥内容。
4. 重启或重建容器后密钥内容不变。
5. 显式传入 `DJANGO_SECRET_KEY` 时应用优先使用显式值。
6. 应用健康检查返回 HTTP 200 和 `{"status":"ok"}`。
7. README 命令与实际部署流程一致。
