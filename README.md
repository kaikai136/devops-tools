# 运维工具 Django + Vue3 重构版

这是基于现有 Tauri 版本功能整理出的 Web 重构版本，采用 Django REST API + Vue 3 + Vite。

## 目录结构

```text
django-vue/
├── backend/          # Django API 服务
└── frontend/         # Vue 3 前端
```

## 后端启动

```bash
cd django-vue/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

## 前端启动

```bash
cd django-vue/frontend
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

## 已迁移功能

- IP 探活
- 端口探测
- 快速端口测试
- Ping 工具
- IPv4 子网划分
- 双因子认证 TOTP 管理
- 密码生成器
- 历史记录和本地数据 API
