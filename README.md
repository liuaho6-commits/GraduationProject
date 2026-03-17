# 🎓 毕业设计：基于矩阵优化与Spark分布式的A股多因子量化回测系统 (开发者与 AI 架构指南)

> **⚠️ 致 AI 开发助手的系统指令 (System Prompt for AI)**：
> 当你阅读到此文档时，请严格遵循 **"Evidence-First Development (证据先行)"** 原则。在修改任何后端逻辑或数据库状态前，必须先编写独立的 Python 调试脚本 (`debug_xxx.py`) 验证数据真实性与时区上下文。系统中存在高度耦合的“模拟时间流”与“高频资金锁”，严禁主观假设！

---

## 🏗️ 1. 系统核心架构与技术栈
本项目是一个包含“历史回测”与“模拟实盘”的完整量化平台。
* **前端 (quant_frontend)**: Vue 3 (Composition API) + Vite + Element-Plus + ECharts。
* **后端 (quant_backend)**: Django 4.x + Django REST Framework (DRF) + SQLite/MySQL。
* **量化引擎**: Apache Spark (PySpark分布式回测) + Numpy/Pandas (矩阵截面打分)。
* **时间系统**: 基于 `mock_time.json` 的全局虚拟时间流引擎，所有业务严格按照模拟时间推进。

---

## 🧩 2. 后端模块分工 (Django Apps)

### 2.1 `trade` (交易撮合与策略执行引擎) - **核心大脑**
* **分工**: 负责实盘订单撮合、持仓计算、自动化多因子策略执行、时间流控制。
* **核心业务逻辑**:
  * **定时引擎 (`tasks.py` & `engine.py`)**: 秒级时钟 `clock_tick` 驱动。在开盘 `09:30` 和尾盘 `14:50` 唤醒引擎，获取活跃策略进行自动调仓。带有 `run_records` 防重复执行锁。
  * **实盘多因子引擎 (`executor.py`)**: 抛弃传统逐只遍历，利用 Numpy 对全市场最近 6 天数据提取截面因子（动量、偏离度），进行 Z-Score 标准化，得出得分矩阵后生成买卖订单。
  * **高频并发锁**: 撮合交易时强制使用 `select_for_update()` 与 `transaction.atomic()` 悲观锁，防止超卖爆仓。
  * **智能休市判定**: 基于“数据库事实”——若 `StockMinuteData` 无当日数据，即判定为休市，前端拒绝渲染虚假分时线。

### 2.2 `backtest` (Spark 分布式回测引擎)
* **分工**: 接收前端多因子权重配置，调度 PySpark 集群对海量历史数据进行并行回测。
* **核心机制**: 返回资金净值曲线 (`equity_curve`) 与 每日持仓调仓记录 (`positions_history`)。

### 2.3 `users` (用户资产与状态中心)
* **分工**: 维护用户账号、资金余额 (`balance`)、总资产缓存 (`last_total_assets`) 以及日收益对齐计算。

### 2.4 `stocks` (基础行情数据中心)
* **分工**: 存储日线 (`StockData`) 和五分钟线 (`StockMinuteData`)。

---

## 🔌 3. 核心 API 接口指南 (RESTful API)

### 3.1 用户与资产 (`users` 模块)
* **`GET /api/users/info/`**
  * **功能**: 获取用户资产大盘。
  * **AI 注意点**: 调用时会触发 `update_asset_cache()`。返回的 `daily_profit` 是强制基于 `(当前总资产 - 昨天收盘资产)` 实时计算的，与前端图表严丝合缝对齐。

### 3.2 模拟时间与系统控制 (`trade` 模块)
* **`GET /trade/api/time/`** * **功能**: 获取系统当前模拟时间。
* **`POST /trade/api/control/`**
  * **功能**: 上帝控制台，操作 `{action: 'set_time', target_time: '2024-03-21'}` 进行时间跃迁。

### 3.3 交易与持仓 (`trade` 模块)
* **`GET /trade/api/performance/?type=intraday|daily`**
  * **功能**: 渲染资金收益曲线。
  * **AI 注意点**: `intraday` 为 5 分钟步长倒推算法，且末尾点强制与 UserProfile 总资产缝合；`daily` 为直接查询 `DailyPerformance` 数据库表。如果当日 `intraday` 查不到分钟线数据，直接返回 `[]` 触发前端休市遮罩。
* **`POST /api/trade/order/`**
  * **功能**: 手动下单接口。
* **`GET /api/trade/positions/`**
  * **功能**: 获取当前真实持仓列表，每次调用会自动触发 `sync_positions` 校准幽灵仓位。

### 3.4 策略与自动交易 (`trade` 模块)
* **`GET /api/trade/strategy/`**
  * **功能**: 获取用户的多因子实盘策略列表。
* **`POST /api/trade/strategy/`**
  * **功能**: 创建/修改/启停策略。
  * **🔥 AI 避坑重灾区**: `Strategy` 模型的 `code` 字段**不存储 Python 字符串代码**！它存储的是 JSON 格式的多因子权重配置，例如：`{"weight_mom": 0.5, "weight_bias": -0.4, "top_n": 2}`。引擎会解析该 JSON 进行矩阵选股。

### 3.5 分布式回测 (`backtest` 模块)
* **`POST /api/backtest/run/`**
  * **Payload**: `{task_name, start_date, end_date, initial_capital, weight_mom, weight_bias, top_n}`
  * **功能**: 启动 Spark 回测任务，返回统计指标及图表数据。支持在前端“一键部署”为 `trade` 模块的实盘策略。

---

## 📊 4. 关键数据库模型映射 (Models)

1. **`trade.Strategy`**
   * `status`: 'active' (运行中) / 'stopped' (停止)。
   * `code`: 存储 JSON 因子配置。
   * `stock_pool`: 交易股票池，逗号分隔。
2. **`users.UserProfile`**
   * `balance`: 绝对可用现金。
   * `last_total_assets`: 最新总资产（现金+市值），由缓存函数实时更新。
3. **`trade.DailyPerformance`**
   * 用于记录每日 15:00 结算时的资产快照。是分时图和仪表盘计算“昨日基准资产”的核心依据。
4. **`stocks.StockData` & `stocks.StockMinuteData`**
   * **严防未来函数**: 所有读取行情的 QuerySet 必须带有 `date__lte=get_mock_now()` 限制，绝不能使用系统真实时间 (`timezone.now()`)。

---

## 🖥️ 5. 前端视图与组件地图 (Vue 3)

* **`src/views/DashboardView.vue`**: 交易主控台。组合了资产概览、图表、持仓和实盘策略管理。
* **`src/views/BacktestView.vue`**: 回测面板。配置参数 -> 调用 Spark -> ECharts 渲染收益曲线和回撤 -> 提供“一键部署为实盘策略”按钮。
* **`src/components/AssetOverview.vue`**: 顶部资产卡片，显示总资产与当日/累计收益。
* **`src/components/PerformanceChart.vue`**: 包装组件，内部切换 `IntradayPerformanceChart` (含智能休市遮罩) 与 `DailyPerformanceChart`。
* **`src/components/MyStrategies.vue`**: 实盘多因子策略管理面板，通过滑动条调整 JSON 因子参数并激活引擎。

---

## 🚀 6. 开发环境部署指南

1. **后端启动**:
```bash
cd quant_backend
pip install -r requirements.txt
# 启动 Web API 服务
python manage.py runserver 
# 启动 秒级模拟时间流与策略调度引擎 (必须独立开一个终端)
python manage.py run_scheduler