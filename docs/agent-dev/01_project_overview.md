# 项目总览

本文档面向后续 AI agent 调试使用，重点记录当前源码中可验证的结构、入口和容易踩坑的机制。除特别标注“待确认”的内容外，结论均来自当前仓库源码路径。

## 1. 项目用途和业务背景

本项目是一个 A 股多因子量化交易与回测系统，包含行情浏览、用户模拟资金账户、手动模拟交易、实盘风格的自动调仓策略、Spark 本地分布式回测和大盘指数展示。

核心业务链路：

1. 股票/指数行情数据写入数据库，主要模型在 `quant_backend/stocks/models.py`。
2. 前端展示行情、资产、持仓、订单、策略和回测结果，入口在 `quant_frontend/src/main.js` 和 `quant_frontend/src/router/index.js`。
3. 后端使用 Django REST API 提供用户、行情、交易、回测接口，总路由在 `quant_backend/quant_backend/urls.py`。
4. 交易模块读取模拟时间，基于用户策略配置进行多因子选股和订单撮合，核心在 `quant_backend/trade/time_utils.py`、`quant_backend/trade/engine.py`、`quant_backend/trade/executor.py`。
5. 回测模块读取日线行情，用 PySpark 计算动量和均线偏离因子，返回资金曲线和持仓历史，核心在 `quant_backend/backtest/engine.py`、`quant_backend/backtest/views.py`。

业务背景资料还可参考：

- `README.md`：包含架构说明和 AI 调试注意事项，但部分启动说明与当前源码存在不一致，需以源码为准。
- `项目设计.md`：早期设计文档，提到模拟撮合、策略沙箱、管理员后台、用户转账等目标。
- `quant_backend/后端模块功能介绍.txt`：后端模块说明，部分描述可能滞后于当前实现。

## 2. 前端、后端、数据库、脚本分工

### 前端

前端位于 `quant_frontend/`，是 Vue 3 + Vite + Element Plus + ECharts 项目。

关键文件：

- `quant_frontend/package.json`：前端脚本为 `dev`、`build`、`preview`。
- `quant_frontend/src/main.js`：创建 Vue app，注册 Pinia、Vue Router、Element Plus 和图标。
- `quant_frontend/src/router/index.js`：页面路由和 token 登录守卫。
- `quant_frontend/src/layout/MainLayout.vue`：登录后主布局，包含仪表盘、行情中心、量化回测菜单。

主要页面和组件：

- `quant_frontend/src/views/DashboardView.vue`：仪表盘，聚合资产、收益图、策略、持仓、订单，并轮询 `/api/users/info/`、`/trade/api/orders/`、`/trade/api/time/`。
- `quant_frontend/src/views/MarketView.vue`：行情中心，调用 `stocks/api/market/` 和自选股接口。
- `quant_frontend/src/views/StockDetailView.vue`：股票详情页，读取股票日线/分钟线并提供交易面板。
- `quant_frontend/src/views/MarketIndexDetailView.vue`：大盘指数详情页。
- `quant_frontend/src/views/BacktestView.vue`：多因子回测页面，调用 `/api/backtest/run/`，并可将回测参数部署为实盘策略。
- `quant_frontend/src/components/MyStrategies.vue`：策略管理面板，`Strategy.code` 在前端保存为 JSON 字符串，不是 Python 代码。
- `quant_frontend/src/components/TradePanel.vue`、`quant_frontend/src/components/TradeDialog.vue`：手动交易入口，调用 `/api/trade/place_order/`。
- `quant_frontend/src/components/PerformanceChart.vue`、`DailyPerformanceChart.vue`、`IntradayPerformanceChart.vue`：收益图表。

前端 API 地址目前硬编码为 `http://127.0.0.1:8000/`，可在多个文件中看到，例如 `quant_frontend/src/views/DashboardView.vue`、`quant_frontend/src/views/BacktestView.vue`、`quant_frontend/src/views/MarketView.vue`。

### 后端

后端位于 `quant_backend/`，是 Django 4.2 + Django REST Framework 项目。

关键入口：

- `quant_backend/manage.py`：Django 管理命令入口。
- `quant_backend/quant_backend/settings.py`：全局配置，启用 `stocks`、`users`、`managers`、`trade`、`backtest`、`django_apscheduler`。
- `quant_backend/quant_backend/urls.py`：总路由，挂载 `trade/api/`、`api/trade/`、`users/api/`、`api/users/`、`stocks/`、`api/backtest/`。

Django apps 分工：

- `quant_backend/stocks/`：股票、指数基础信息与行情数据接口。
- `quant_backend/users/`：注册、登录、Token、用户资产、自选股。
- `quant_backend/trade/`：模拟时间、资金划转、手动下单、持仓、订单、策略管理、自动策略执行、收益曲线。
- `quant_backend/backtest/`：Spark 回测任务、回测结果、回测接口。
- `quant_backend/managers/`：管理员登录、统计、用户列表接口。待确认：该 app 当前未挂载到 `quant_backend/quant_backend/urls.py`，所以 `managers/urls.py` 中的接口默认不可达。

### 数据库

数据库配置在 `quant_backend/quant_backend/settings.py`：

- 引擎：`django.db.backends.mysql`
- 数据库名：`quant_db`
- host/port：`127.0.0.1:3306`
- 用户：`root`
- 密码：源码中写死为 `liuhao`，调试时注意这不是安全配置。

主要模型：

- `stocks.StockData`：日线行情，表名 `stock_data_daily`，见 `quant_backend/stocks/models.py`。
- `stocks.StockMinuteData`：分钟行情，表名 `stock_data_minute`，见 `quant_backend/stocks/models.py`。
- `stocks.StockBasicInfo`：股票基础信息，见 `quant_backend/stocks/models.py`。
- `stocks.MarketIndexBasicInfo`、`MarketIndexDailyData`、`MarketIndexMinuteData`：指数基础、日线、分钟数据，见 `quant_backend/stocks/models.py`。
- `users.UserProfile`：用户资金、资产缓存、收益缓存，见 `quant_backend/users/models.py`。
- `users.UserFavorite`：自选股，见 `quant_backend/users/models.py`。
- `trade.Strategy`：实盘策略配置，`code` 字段当前存 JSON 多因子参数，见 `quant_backend/trade/models.py`。
- `trade.Position`：用户持仓，见 `quant_backend/trade/models.py`。
- `trade.Order`：委托订单，见 `quant_backend/trade/models.py`。
- `trade.TradeRecord`：成交流水，见 `quant_backend/trade/models.py`。
- `trade.DailyPerformance`、`trade.IntradayPerformance`：日收益和日内资产快照，见 `quant_backend/trade/models.py`。
- `trade.SystemSettings`：模拟时间和时间流速，见 `quant_backend/trade/models.py`。
- `backtest.Factor`、`BacktestTask`、`BacktestResult`：因子、回测任务、回测结果，见 `quant_backend/backtest/models.py`。

### 脚本和数据目录

数据和脚本分散在根目录、`stocks/management/commands/` 和后端根目录。

数据目录：

- `raw_data（沪深3000）/`：大量股票 CSV 文件。
- `raw_data/`：待确认，需按具体文件核实。
- `hs300_data_center/data/`：待确认，名称暗示沪深 300 数据中心。
- `history_k_data.csv`：根目录历史 K 线数据文件，具体用途待确认。

后端脚本：

- `quant_backend/download_hs300_to_db.py`：使用 baostock/pandas 导入沪深 300 相关日线/分钟线到数据库，源码中有事务和批量写入逻辑。
- `quant_backend/stocks/management/commands/download_real_3y.py`：使用 baostock 下载指定股票 5 分钟线，会清空 `StockMinuteData`。
- `quant_backend/stocks/management/commands/init_minute_data.py`：使用 akshare 初始化指定股票近 3 年日线和分钟线，会交互确认并清空 `StockData`、`StockMinuteData`、`StockBasicInfo`。
- `quant_backend/stocks/management/commands/fill_mock_data.py`：使用 akshare 下载真实数据，并对缺失分钟线用布朗桥模拟补齐，会交互确认并清空行情基础表。
- `quant_backend/stocks/management/commands/download_market_index_data.py`：下载大盘指数数据，使用 akshare/pandas，写入指数相关模型。
- `quant_backend/debug.py`、`quant_backend/quant_backend/debug_future_volume.py`：调试脚本，后者疑似存在字段名不匹配风险，需运行前核实。

## 3. 主要目录结构

```text
E:\GraduationProject
├── README.md
├── 项目设计.md
├── history_k_data.csv
├── raw_data（沪深3000）/
├── raw_data/
├── hs300_data_center/
│   └── data/
├── quant_frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── router/index.js
│       ├── layout/MainLayout.vue
│       ├── views/
│       ├── components/
│       └── stores/user.js
└── quant_backend/
    ├── manage.py
    ├── mock_time.json
    ├── quant_backend/
    │   ├── settings.py
    │   └── urls.py
    ├── stocks/
    ├── users/
    ├── trade/
    ├── backtest/
    └── managers/
```

调试时优先把 `quant_frontend/` 和 `quant_backend/` 当作两个独立项目看待。

## 4. 启动方式和常见入口文件

### 前端启动

从 `quant_frontend/package.json` 可确认：

```bash
cd quant_frontend
npm install
npm run dev
```

构建和预览：

```bash
npm run build
npm run preview
```

### 后端启动

后端是 Django 项目，入口为 `quant_backend/manage.py`：

```bash
cd quant_backend
python manage.py runserver
```

依赖安装方式待确认：仓库中未发现 `requirements.txt` 或 `pyproject.toml`。根据源码可推断至少需要 Django、djangorestframework、django-cors-headers、django-apscheduler、PySpark、pandas、numpy、akshare、baostock、tqdm 和 MySQL 驱动，但具体版本待确认。

数据库迁移常规入口：

```bash
python manage.py migrate
```

创建管理员常规入口：

```bash
python manage.py createsuperuser
```

### 调度器入口

当前源码存在新旧两套调度入口，需特别注意：

- 当前更可能生效的入口：`quant_backend/trade/apps.py` 的 `TradeConfig.ready()`，当 `RUN_MAIN == 'true'` 时调用 `quant_backend/trade/scheduler.py:start_scheduler()`。
- `quant_backend/trade/scheduler.py` 每秒触发 `trade.tasks.clock_tick()`，负责推进模拟时间、记录 5 分钟快照、收盘结算和运行策略。
- 疑似失效入口：`quant_backend/trade/management/commands/run_scheduler.py` 导入 `run_active_strategies`、`record_intraday_assets`，但当前 `quant_backend/trade/tasks.py` 中没有这两个函数。
- `quant_backend/trade/apps.py` 里的 `start_scheduler()` 方法也引用了同样不存在的旧函数，但 `ready()` 当前调用的是 `trade.scheduler.start_scheduler()`，不是类方法。仍建议调试调度问题时先核实 Django 实际加载的 AppConfig。

根 `README.md` 提到 `python manage.py run_scheduler`，但按当前源码看该命令大概率会导入失败，标记为待确认。

## 5. API 路由入口

总路由见 `quant_backend/quant_backend/urls.py`。

用户接口：

- `POST /api/users/login/`、`POST /users/api/login/`：登录，见 `quant_backend/users/views.py`。
- `POST /api/users/register/`、`POST /users/api/register/`：注册，见 `quant_backend/users/views.py`。
- `GET /api/users/info/`、`GET /users/api/info/`：用户资产信息，会调用 `UserProfile.update_asset_cache()`，见 `quant_backend/users/views.py` 和 `quant_backend/users/models.py`。
- `/api/users/favorites/`、`/users/api/favorites/`：自选股，见 `quant_backend/users/urls.py`。

行情接口：

- `GET /stocks/api/market/`：行情列表，见 `quant_backend/stocks/views.py:get_market_list_api`。
- `GET /stocks/api/data/<stock_code>/`：股票 K 线，支持 `freq=daily|min`，见 `quant_backend/stocks/views.py:get_stock_data_api`。
- `GET /stocks/api/indices/`：指数概览，见 `quant_backend/stocks/views.py:get_market_index_list_api`。
- `GET /stocks/api/index/<index_code>/`：指数 K 线，支持 `freq=daily|min|5min`，见 `quant_backend/stocks/views.py:get_market_index_data_api`。

交易接口：

- `GET /trade/api/time/` 和 `GET /api/trade/time/`：当前模拟时间，见 `quant_backend/trade/views.py:SystemTimeView`。
- `POST /trade/api/control/` 和 `POST /api/trade/control/`：设置时间/速度，见 `quant_backend/trade/views.py:SystemControlView`。
- `GET /trade/api/performance/?type=daily|intraday` 和 `/api/trade/performance/`：收益曲线，见 `quant_backend/trade/views.py:PerformanceView`。
- `POST /api/trade/place_order/`：手动下单，见 `quant_backend/trade/views.py:PlaceOrderView`。
- `GET /api/trade/positions/`：持仓列表，见 `quant_backend/trade/views.py:PositionListView`。
- `GET/POST/DELETE /api/trade/strategy/`：策略列表、创建/更新、删除，见 `quant_backend/trade/views.py:StrategyView`。
- `GET /api/trade/orders/`：最近订单，见 `quant_backend/trade/views.py:OrderListView`。
- `POST /api/trade/transfer/`：模拟资金划转，见 `quant_backend/trade/views.py:FundTransferView`。

回测接口：

- `POST /api/backtest/run/`：运行回测，见 `quant_backend/backtest/urls.py` 和 `quant_backend/backtest/views.py:RunBacktestView`。

## 6. Agent 调试时最应该先看的文件

如果是启动/环境问题，优先看：

- `quant_backend/quant_backend/settings.py`：数据库、已安装 app、DRF Token、CORS。
- `quant_backend/quant_backend/urls.py`：接口前缀是否与前端一致。
- `quant_frontend/package.json`：前端脚本。
- `quant_frontend/vite.config.js`：当前没有代理配置，前端多处硬编码后端地址。
- `quant_backend/trade/apps.py`、`quant_backend/trade/scheduler.py`、`quant_backend/trade/tasks.py`：调度器是否自动启动、是否引用旧函数。

如果是登录/用户/资产问题，优先看：

- `quant_backend/users/views.py`：登录、注册、用户信息接口。
- `quant_backend/users/models.py:UserProfile.update_asset_cache()`：总资产、当日收益、可取资金计算。
- `quant_backend/users/serializers.py`：自选股行情快照逻辑。
- `quant_frontend/src/views/LoginView.vue`、`RegisterView.vue`、`DashboardView.vue`。

如果是行情/K 线问题，优先看：

- `quant_backend/stocks/models.py`：日线、分钟线、指数模型字段。
- `quant_backend/stocks/views.py`：行情接口全部逻辑，尤其 `get_mock_now()` 限制和“未来数据”过滤。
- `quant_backend/stocks/urls.py`：行情接口路径。
- `quant_frontend/src/views/MarketView.vue`、`StockDetailView.vue`、`MarketIndexDetailView.vue`。

如果是交易/持仓/订单问题，优先看：

- `quant_backend/trade/views.py:PlaceOrderView`：手动下单，使用 `transaction.atomic()` 和 `select_for_update()` 锁用户资金。
- `quant_backend/trade/views.py:sync_positions()`：根据已成交订单重建持仓，可能覆盖 `Position.avg_price` 信息。
- `quant_backend/trade/views.py:PositionListView`：当前价、市值、盈亏计算。
- `quant_backend/trade/models.py`：订单、持仓、成交、收益模型。
- `quant_frontend/src/components/TradePanel.vue`、`PositionList.vue`、`RecentOrders.vue`。

如果是策略/自动交易问题，优先看：

- `quant_backend/trade/models.py:Strategy`：策略字段定义。
- `quant_backend/trade/views.py:StrategyView`：策略 CRUD。
- `quant_backend/trade/engine.py`：开盘/尾盘窗口、run_records 防重复、落地订单与撮合。
- `quant_backend/trade/executor.py`：JSON 参数解析、股票池解析、Numpy Z-Score 打分、调仓信号生成。
- `quant_frontend/src/components/MyStrategies.vue`：前端如何保存策略配置。
- `quant_frontend/src/views/BacktestView.vue:deployToRealTrade()`：回测部署为实盘策略的 payload。

如果是收益曲线/结算问题，优先看：

- `quant_backend/trade/tasks.py:record_intraday_snapshot()`：5 分钟资产快照。
- `quant_backend/trade/tasks.py:record_daily_performance()`：每日收盘结算。
- `quant_backend/trade/views.py:PerformanceView`：日线/分时收益图计算和当前点缝合逻辑。
- `quant_backend/users/models.py:UserProfile.update_asset_cache()`：顶部资产卡片的数据来源。
- `quant_frontend/src/components/DailyPerformanceChart.vue`、`IntradayPerformanceChart.vue`、`PerformanceChart.vue`。

如果是回测问题，优先看：

- `quant_backend/backtest/engine.py`：Spark 初始化、行情加载、多因子计算、模拟组合收益。
- `quant_backend/backtest/views.py`：接口参数、任务落库、结果格式化、股票名称映射。
- `quant_backend/backtest/models.py`：回测任务和结果字段。
- `quant_frontend/src/views/BacktestView.vue`：表单参数、图表、回测部署策略。

## 7. 已知特殊机制和调试注意事项

### 模拟时间

当前业务主路径使用数据库 `trade.SystemSettings.current_mock_time` 作为模拟时间源：

- 获取时间：`quant_backend/trade/time_utils.py:get_mock_now()`。
- 设置时间：`quant_backend/trade/time_utils.py:set_mock_now()` 和 `quant_backend/trade/views.py:SystemControlView`。
- 时间流速：`trade.SystemSettings.time_speed`，每个 `clock_tick()` 增加 `time_speed` 秒，见 `quant_backend/trade/tasks.py`。
- `quant_backend/mock_time.json` 当前存在，内容为 `{"time": "2026-01-07T13:46:00+00:00"}`，但当前 grep 未发现业务主路径读取该文件。根 `README.md` 中关于 `mock_time.json` 的描述可能是旧机制，标记为待确认。

设置时间的副作用很大：

- `SystemControlView` 的 `set_time` 会调用 `SystemSettings.hard_reset_world()`，见 `quant_backend/trade/views.py` 和 `quant_backend/trade/models.py`。
- `hard_reset_world()` 会删除 `Order`、`Position`、`DailyPerformance`、`IntradayPerformance`，并重置所有 `UserProfile` 的资金和收益字段。
- 调试时间跳转前必须确认是否允许清空交易状态。

### 行情数据和未来函数防护

多数行情读取都依赖模拟时间：

- 股票详情日线：`StockData.date__lte=mock_date`，见 `quant_backend/stocks/views.py:get_stock_data_api`。
- 股票详情分钟线：先宽松查询到模拟时间后一天，再在内存中过滤 `item_naive <= mock_naive`，见 `quant_backend/stocks/views.py:get_stock_data_api`。
- 行情列表：优先取 `StockMinuteData` 中不晚于模拟时间的近 5 分钟数据，回退日线，见 `quant_backend/stocks/views.py:get_market_list_api`。
- 指数数据同样限制在 `mock_now` 或 `mock_date` 之前，见 `quant_backend/stocks/views.py`。

调试行情“不显示”时先核实：

- 数据表里是否有该日期/股票/指数数据。
- `SystemSettings.current_mock_time` 是否落在数据范围内。
- 分钟线时区是否与 `timezone.make_naive()` 过滤逻辑一致。

### 交易撮合

手动交易：

- 入口 `quant_backend/trade/views.py:PlaceOrderView`。
- 买入会锁定 `UserProfile`，扣减 `balance`，更新或创建 `Position`，按移动加权计算 `avg_price`。
- 卖出会检查 `Position.volume`，减少持仓并增加 `balance`。
- 成交订单状态直接创建为 `filled`，使用模拟时间 `get_mock_now()` 写入 `Order.order_time`。
- 当前手动交易不创建 `TradeRecord`，只创建 `Order`。策略自动交易会创建 `TradeRecord`，见 `quant_backend/trade/engine.py`。这会影响依赖 `TradeRecord` 的工具函数。

自动策略交易：

- 入口 `quant_backend/trade/engine.py:TradingEngine.run_all_active_strategies()`。
- 只在模拟时间 `09:30-09:35` 或 `14:50-14:59` 触发。
- `run_records` 在进程内按日期和 open/close 防重复执行；重启进程后该内存锁会丢失。
- 撮合时使用 `transaction.atomic()`、`UserProfile.objects.select_for_update()` 和 `Position.objects.select_for_update()`，见 `quant_backend/trade/engine.py`。

持仓同步：

- `quant_backend/trade/views.py:sync_positions()` 会根据已成交 `Order` 回放出真实持仓，并写回 `Position.volume`。
- 该函数在 `PlaceOrderView`、`PositionListView`、`PositionDetailView` 中调用。
- 注意：`sync_positions()` 更新持仓时只写 `volume`，可能不会重建正确 `avg_price`，调试盈亏异常时要检查该副作用。

### 多因子策略机制

当前实盘策略不是执行用户 Python 代码，而是读取 JSON 参数做多因子矩阵选股：

- `Strategy.code` 字段名虽然叫“策略代码”，但当前前端保存为 JSON 字符串，如 `{"weight_mom":0.6,"weight_bias":-0.4,"top_n":2}`，见 `quant_frontend/src/components/MyStrategies.vue` 和 `quant_frontend/src/views/BacktestView.vue`。
- 后端在 `quant_backend/trade/executor.py:StrategyExecutor.execute()` 中解析 `strategy.code`。
- 股票池来自 `Strategy.stock_pool`，支持逗号分隔，也支持全市场哨兵值：`__ALL__`、`ALL`、`ALL_STOCKS`、`全部`、`全部股票`，见 `quant_backend/trade/executor.py`。
- 因子为动量 `momentum=(close_0-close_1)/close_1` 和 5 日均线偏离 `bias=(close_0-ma5)/ma5`，然后用 Numpy 做截面 Z-Score，见 `quant_backend/trade/executor.py`。
- 调仓逻辑为卖出不在 Top N 的现有持仓，并把当前现金按 Top N 平均分配给未持有入选标的，买入数量按 100 股取整，见 `quant_backend/trade/executor.py`。

旧设计文档中提到基于 `exec` 的 Python 策略沙箱，见 `项目设计.md`。当前主源码未发现该沙箱路径，标记为旧机制/待确认。

### 回测机制

回测入口为 `POST /api/backtest/run/`，见 `quant_backend/backtest/views.py`。

流程：

1. 接收 `task_name`、`start_date`、`end_date`、`initial_capital`、`weight_mom`、`weight_bias`、`top_n`。
2. 创建 `BacktestTask`，用户取 `User.objects.first()`，不是当前登录用户；接口权限为 `AllowAny`，见 `quant_backend/backtest/views.py`。
3. `SparkBacktestEngine` 使用 `SparkSession.master("local[*]")` 在本机运行，见 `quant_backend/backtest/engine.py`。
4. 从 `StockData` 读取日期范围内所有日线 close，转 pandas 再转 Spark DataFrame。
5. 计算动量、5 日均线偏离、T+1 收益、截面 Z-Score 和综合得分。
6. 每日取 Top N 股票，组合收益取 `next_return` 均值，生成资金曲线。
7. 写入 `BacktestResult.equity_curve` 和 `positions_history`。

回测注意事项：

- 回测只使用日线 `StockData`，不使用分钟线。
- `max_drawdown`、`sharpe_ratio`、`win_rate` 模型字段存在，但当前 `RunBacktestView` 未计算写入。
- Spark 初始化设置了 Windows 兼容环境变量 `PYSPARK_PYTHON`、`PYSPARK_DRIVER_PYTHON`、`SPARK_LOCAL_IP`，见 `quant_backend/backtest/engine.py`。
- `SparkBacktestEngine.stop()` 在成功路径调用；异常路径是否释放 Spark 待确认。

### 收益曲线和休市判定

日线收益：

- `PerformanceView` 的 `type=daily` 查询 `DailyPerformance`，如今天无记录则用 `calculate_asset_status()` 补一个今日点，见 `quant_backend/trade/views.py`。

分时收益：

- `PerformanceView` 的 `type=intraday` 不直接读 `IntradayPerformance`，而是按 5 分钟步长倒推现金和持仓，并在最后用 `profile.update_asset_cache()` 缝合当前资产点，见 `quant_backend/trade/views.py`。
- 如果当日数据库中完全没有 `StockMinuteData`，直接返回空数组，前端可显示休市/无数据状态，见 `quant_backend/trade/views.py`。

收盘结算：

- `trade.tasks.clock_tick()` 在时间跨过 15:00 或日期变化时调用 `record_daily_performance()`，见 `quant_backend/trade/tasks.py`。
- `record_daily_performance()` 会遍历所有 `UserProfile`，触发 `update_asset_cache()`，写入 `DailyPerformance`，并清理旧 `IntradayPerformance`，见 `quant_backend/trade/tasks.py`。

### 已知不一致和疑似问题

- `quant_backend/README.md` 不存在，后端说明在 `quant_backend/后端模块功能介绍.txt`。
- 根 `README.md` 提到 `mock_time.json`，但当前模拟时间主路径是数据库 `SystemSettings`，待确认是否仍有外部脚本读写 `mock_time.json`。
- 根 `README.md` 提到 `python manage.py run_scheduler`，但当前 `run_scheduler.py` 引用了 `trade.tasks.run_active_strategies` 和 `record_intraday_assets`，这两个函数不存在，疑似失效。
- `trade.apps.py` 的类方法 `start_scheduler()` 也引用旧任务函数，但当前 `ready()` 调用的是 `trade.scheduler.start_scheduler()`；如果调度器没有启动，先核实 AppConfig 自动加载和 `RUN_MAIN`。
- `SystemControlView.get()` 返回 `settings.skip_non_trading`，但 `SystemSettings` 模型中该字段已删除，调用该 GET 接口可能报错，见 `quant_backend/trade/views.py` 和 `quant_backend/trade/models.py`。
- `quant_backend/package.json` 只含前端依赖片段，后端 Python 依赖未被记录为标准依赖文件，待确认。
- `managers/urls.py` 存在管理员接口，但总路由未 include，默认不可访问，待确认是否有另一个前端/路由入口。
- `PlaceOrderView` 手动下单不创建 `TradeRecord`，但 `trade/utils.py` 中部分函数基于 `TradeRecord` 回放，调试历史资产时需区分手动单和策略单。
