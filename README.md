<<<<<<< HEAD
# GraduationProject（量化交易平台）本地运行指南

## 目录结构

- `quant_backend/`：Django 后端（REST API + APScheduler 定时任务）
- `quant_frontend/`：Vue3 + Vite 前端
- `env/`：本地/容器数据（你当前的 MySQL 数据卷也在这里）
- `raw_data/`：原始数据与导入脚本

## 前置条件

- **Windows 10/11 + WSL2**
- **Docker（运行在 WSL）**：你的 MySQL 已经在 WSL 的 Docker 里启动
- **Conda 环境**：后端使用 `stock_pyspark`
- **Node.js**：前端需要（建议 Node 18+ / 20+）

## 1) 数据库（WSL Docker MySQL）

后端当前默认连接配置写在 `quant_backend/quant_backend/settings.py`：

- Host：`127.0.0.1`
- Port：`3306`
- DB：`quant_db`
- User：`root`
- Password：`liuhao`

你需要确保 **WSL 的 MySQL 容器把 3306 映射到 Windows 本机 3306**（例如 `-p 3306:3306`），并且库名为 `quant_db`。

> 如果你映射的端口/密码不同，直接改 `settings.py` 里 `DATABASES['default']` 对应字段即可。

## 2) 启动后端（Django）

在 Windows PowerShell 中执行：

```bash
cd E:\GraduationProject\quant_backend

# 依次检查 / 迁移（首次建议跑一遍）
conda run -n stock_pyspark --no-capture-output python manage.py check
conda run -n stock_pyspark --no-capture-output python manage.py migrate

# 启动开发服务器（默认 8000）
conda run -n stock_pyspark --no-capture-output python manage.py runserver 0.0.0.0:8000
```

启动成功后访问：

- 后端：`http://127.0.0.1:8000/`
- Django Admin：`http://127.0.0.1:8000/admin/`

如需创建管理员：

```bash
cd E:\GraduationProject\quant_backend
conda run -n stock_pyspark --no-capture-output python manage.py createsuperuser
```

## 3) 启动前端（Vue3 + Vite）

```bash
cd E:\GraduationProject\quant_frontend
npm install
npm run dev
```

Vite 默认会在 `5173` 端口启动（以终端输出为准）。

## 4) API 路由速览

后端 `quant_backend/quant_backend/urls.py` 同时提供两套前缀，便于兼容：

- 交易模块（等价）：
  - `/trade/api/...`
  - `/api/trade/...`
- 用户模块（等价）：
  - `/users/api/...`
  - `/api/users/...`
- 股票模块：
  - `/stocks/api/...`

常用接口（示例）：

- **登录/注册**
  - `POST /api/users/login/`
  - `POST /api/users/register/`
  - `GET  /api/users/info/`
- **策略/交易**
  - `GET  /api/trade/performance/`
  - `POST /api/trade/transfer/`
  - `GET|POST /api/trade/strategy/`
  - `GET  /api/trade/positions/`
  - `GET  /api/trade/orders/`
  - `POST /api/trade/place_order/`
- **行情/数据**
  - `GET /stocks/api/market/`
  - `GET /stocks/api/data/<stock_code>/`

## 常见问题

### 1) 前端跨域

后端已配置 `CORS_ALLOW_ALL_ORIGINS = True`，本地开发通常不需要额外处理。

### 2) 访问 `0.0.0.0:8000` vs `127.0.0.1:8000`

- 浏览器访问请用：`http://127.0.0.1:8000/`
- `0.0.0.0` 只是监听地址，方便局域网/容器场景。

=======
# GraduationProject
毕设
>>>>>>> fc91727defefc576a26523badb55b0d8b1a24b27
