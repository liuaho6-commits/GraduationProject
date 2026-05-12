# 常见故障排查手册

本文面向后续 AI agent。排查时遵循证据先行：先确认接口、数据库事实、模拟时间和依赖状态，再判断是否需要修改代码。除非用户明确要求，不要执行删除、重置、覆盖数据的命令。

所有命令默认在项目根目录 `E:\GraduationProject` 下执行；后端命令需要进入 `quant_backend`，前端命令需要进入 `quant_frontend`。

## 1. 后端启动失败

### 现象

`python manage.py runserver` 启动报错，常见表现为 Django 无法导入模块、MySQL 连接错误、端口占用、迁移表不存在，或启动后访问 `http://127.0.0.1:8000/` 返回连接失败。

### 高概率原因

- 后端依赖未安装；仓库中未发现 README 提到的 `quant_backend/requirements.txt`。
- `quant_backend/quant_backend/settings.py` 使用 MySQL：库名 `quant_db`、用户 `root`、密码 `liuhao`、主机 `127.0.0.1`、端口 `3306`，本地 MySQL 未启动或配置不一致。
- `django_apscheduler`、`corsheaders`、`rest_framework`、`rest_framework.authtoken`、MySQL 驱动等缺失。
- 端口 `8000` 已被占用。
- 数据库未迁移，导致 `trade_systemsettings`、`django_apscheduler_*`、`authtoken_token` 等表不存在。

### 排查步骤

1. 确认当前目录和 Python 环境，避免在根目录直接运行 `manage.py`。
2. 用 `python manage.py check` 先做 Django 配置级检查。
3. 检查 MySQL 连接是否可用，再检查迁移状态。
4. 如果报 `ModuleNotFoundError`，按缺失模块反查依赖，而不是直接修改业务代码。
5. 如果涉及策略调度，先检查 `trade/apps.py` 是否通过 `TradeConfig.ready()` 自动启动 `trade.scheduler.start_scheduler()`；当前 `python manage.py run_scheduler` 是疑似失效旧入口，运行前必须核对 `trade/management/commands/run_scheduler.py` 与 `trade/tasks.py` 的函数名是否一致。

### 相关文件

- `quant_backend/manage.py`
- `quant_backend/quant_backend/settings.py`
- `quant_backend/quant_backend/urls.py`
- `quant_backend/trade/apps.py`
- `quant_backend/trade/scheduler.py`
- `quant_backend/trade/tasks.py`
- `quant_backend/trade/management/commands/run_scheduler.py`
- `README.md`

### 可验证命令

```powershell
cd quant_backend
python --version
python manage.py check
python manage.py showmigrations
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.settings_dict['ENGINE']); print('db ok')"
netstat -ano | findstr :8000
```

## 2. 前端接口请求失败

### 现象

前端页面能打开但数据为空，浏览器控制台出现 `Network Error`、`404`、`401`、`CORS`，或请求被发到 Vite 前端端口而不是 Django 后端。

### 高概率原因

- `quant_frontend/vite.config.js` 没有配置代理。
- 前端接口写法不统一：部分请求写死 `http://127.0.0.1:8000/`，部分使用相对路径如 `api/users/info/`、`stocks/api/market/`。
- Django 后端未启动，或后端端口不是 `8000`。
- Token 缺失或请求头未带 `Authorization: Token <token>`。
- 路由前缀混用：后端同时支持 `trade/api/` 和 `api/trade/`，用户接口同时支持 `users/api/` 和 `api/users/`，股票接口挂在 `stocks/api/`。

### 排查步骤

1. 在浏览器 Network 面板确认失败请求的完整 URL、状态码和响应体。
2. 确认后端 `http://127.0.0.1:8000` 可访问。
3. 对比前端请求路径和 `quant_backend/quant_backend/urls.py`、各 app 的 `urls.py`。
4. 对需要登录的接口，确认请求头包含 `Authorization: Token <token>`。
5. 如果相对路径请求失败，优先怀疑 Vite dev server 没有代理，而不是后端接口不存在。

### 相关文件

- `quant_frontend/vite.config.js`
- `quant_frontend/src/views/DashboardView.vue`
- `quant_frontend/src/views/MarketView.vue`
- `quant_frontend/src/views/StockDetailView.vue`
- `quant_frontend/src/views/MarketIndexDetailView.vue`
- `quant_frontend/src/components/TradePanel.vue`
- `quant_backend/quant_backend/urls.py`
- `quant_backend/stocks/urls.py`
- `quant_backend/trade/urls.py`
- `quant_backend/users/urls.py`

### 可验证命令

```powershell
cd quant_backend
python manage.py check
curl.exe -i http://127.0.0.1:8000/stocks/api/market/
curl.exe -i http://127.0.0.1:8000/stocks/api/indices/
cd ..\quant_frontend
npm run build
```

## 3. 登录/Token 问题

### 现象

登录后仍跳回登录页，请求返回 `401 Unauthorized`，资产接口报鉴权失败，或前端提示“登录异常：未获取到令牌”。

### 高概率原因

- 登录接口实际返回结构为 `{ code: 200, data: { token, username } }`，前端解析结构不一致会拿不到 token。
- Token 存在 `localStorage.token`，但 Pinia `useUserStore` 没有同步更新，或页面只写入了 `localStorage`。
- 请求头格式必须是 `Authorization: Token <token>`，不能使用 `Bearer`。
- 后端启用了 DRF `TokenAuthentication`，受保护接口需要有效 token。
- 用户不存在、密码错误、用户被禁用，或 `authtoken_token` 表未迁移。

### 排查步骤

1. 确认登录接口路径是 `/api/users/login/` 或 `/users/api/login/`。
2. 检查浏览器 `localStorage` 是否有 `token`。
3. 在 Network 面板确认后续接口是否带 `Authorization: Token ...`。
4. 后端确认用户数量、Token 表和迁移状态。
5. 如果是前端路由跳转问题，检查 `router.beforeEach` 对 `localStorage.getItem('token')` 的判断。

### 相关文件

- `quant_backend/users/views.py`
- `quant_backend/users/urls.py`
- `quant_backend/quant_backend/settings.py`
- `quant_frontend/src/views/LoginView.vue`
- `quant_frontend/src/stores/user.js`
- `quant_frontend/src/router/index.js`
- `quant_frontend/src/layout/MainLayout.vue`

### 可验证命令

```powershell
cd quant_backend
python manage.py showmigrations authtoken users
python manage.py shell -c "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; print('users', User.objects.count()); print('tokens', Token.objects.count())"
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/api/users/info/
```

## 4. 行情日期不对

### 现象

行情显示的日期不是当前真实日期，页面状态显示休市/交易中与现实不一致，或 K 线看起来停在历史时间。

### 高概率原因

- 系统使用模拟时间，不使用真实系统时间。核心时间来自数据库 `trade.SystemSettings.current_mock_time`，`mock_time.json` 不是当前主要读取来源。
- `get_mock_now()` 在数据库不可用时会回退到 `timezone.now()`，可能掩盖数据库连接问题。
- `settings.py` 中 `TIME_ZONE = "UTC"` 且 `USE_TZ = True`，显示和比较时存在 aware/naive datetime 转换。
- 前端 `DashboardView.vue` 会基于后端返回的 `system_time` 在本地每秒递增显示。
- `SystemControlView` 的 `set_time` 会调用 `hard_reset_world()`，会清空交易数据，不能作为普通排查命令使用。

### 排查步骤

1. 先查询后端 `/trade/api/time/` 返回的模拟时间。
2. 再查询数据库 `SystemSettings.current_mock_time`，确认接口和数据库一致。
3. 检查行情接口响应中的 `current_mock_time`、`latest_time`、`date` 字段。
4. 排查时不要调用 `/trade/api/control/` 的 `set_time`，除非用户明确接受重置交易数据。
5. 如果日期只差时区，重点检查 `timezone.make_naive`、`USE_TZ` 和前端 `new Date()` 解析。

### 相关文件

- `quant_backend/trade/time_utils.py`
- `quant_backend/trade/views.py`
- `quant_backend/trade/models.py`
- `quant_backend/stocks/views.py`
- `quant_backend/quant_backend/settings.py`
- `quant_frontend/src/views/DashboardView.vue`
- `quant_backend/mock_time.json`

### 可验证命令

```powershell
cd quant_backend
python manage.py shell -c "from trade.models import SystemSettings; s=SystemSettings.objects.first(); print(s.current_mock_time if s else 'no SystemSettings')"
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/trade/api/time/
curl.exe -i http://127.0.0.1:8000/stocks/api/indices/
```

## 5. 股票或指数 K 线为空

### 现象

股票详情页或指数详情页图表为空，接口返回 `data: []`，`latest_price` 为 `0`，或只显示“未知股票/未知指数”。

### 高概率原因

- 对应代码在基础信息表不存在：股票用 `StockBasicInfo`，指数用 `MarketIndexBasicInfo`。
- 对应行情表没有数据：股票日线 `stock_data_daily`、股票分钟线 `stock_data_minute`、指数日线 `market_index_daily`、指数分钟线 `market_index_minute`。
- 查询被模拟时间过滤：日线要求 `date <= mock_date`，分钟线要求 `date <= mock_time`。
- 股票分钟线默认最多取最近 500 根有效数据；指数接口受 `limit` 参数影响。
- 股票分时历史查询使用 `date__contains=YYYY-MM-DD`，日期格式或时区不匹配时可能为空。

### 排查步骤

1. 先确认代码格式，例如 `sh.600000`、`sz.300394`、`sh.000300`。
2. 查询基础信息表是否存在对应记录。
3. 查询对应日线和分钟线在模拟时间之前是否有数据。
4. 对指数区分 `freq=daily` 和 `freq=min`；对股票区分 `freq=daily` 和 `freq=min`。
5. 如果接口有数据但前端为空，再检查 ECharts 组件入参格式。

### 相关文件

- `quant_backend/stocks/views.py`
- `quant_backend/stocks/models.py`
- `quant_backend/stocks/serializers.py`
- `quant_backend/stocks/urls.py`
- `quant_frontend/src/views/StockDetailView.vue`
- `quant_frontend/src/views/MarketIndexDetailView.vue`
- `quant_frontend/src/components/StockChart.vue`
- `quant_frontend/src/components/StockMinuteChart.vue`
- `quant_frontend/src/components/StockDailyChart.vue`

### 可验证命令

```powershell
cd quant_backend
python manage.py shell -c "from stocks.models import StockBasicInfo,StockData,StockMinuteData; code='sz.300394'; print('basic', StockBasicInfo.objects.filter(code=code).exists()); print('daily', StockData.objects.filter(code=code).count()); print('minute', StockMinuteData.objects.filter(code=code).count())"
python manage.py shell -c "from stocks.models import MarketIndexBasicInfo,MarketIndexDailyData,MarketIndexMinuteData; code='sh.000300'; print('basic', MarketIndexBasicInfo.objects.filter(code=code).exists()); print('daily', MarketIndexDailyData.objects.filter(code=code).count()); print('minute', MarketIndexMinuteData.objects.filter(code=code).count())"
curl.exe -i http://127.0.0.1:8000/stocks/api/data/sz.300394/?freq=daily
curl.exe -i http://127.0.0.1:8000/stocks/api/index/sh.000300/?freq=daily
```

## 6. 交易下单失败

### 现象

手动买卖提示“交易请求失败”“余额不足”“未持有该股票”“持仓不足”，或接口返回 `交易失败: ...`。

### 高概率原因

- 交易接口需要登录，缺少 `Authorization: Token <token>` 会返回鉴权错误。
- 买入时 `profile.balance < price * volume`。
- 卖出时没有 `Position` 或 `Position.volume < volume`。
- 前端下单接口是 `api/trade/place_order/`，不是 README 中旧写法 `/api/trade/order/`。
- `stock_code`、`direction`、`price`、`volume` 参数缺失或类型错误。
- 下单时会先执行 `sync_positions(user)`，它按已成交订单重算持仓，可能覆盖手工改过的 `trade_position`。

### 排查步骤

1. 确认请求路径 `/api/trade/place_order/` 或 `/trade/api/place_order/`。
2. 检查 token 和请求体字段。
3. 查询用户现金、持仓和最近成交订单。
4. 对卖出失败，确认持仓是否可由历史 `filled` 订单推导出来。
5. 对自动策略下单失败，检查策略状态、股票池、因子配置 JSON 和模拟时间是否处于 `09:30-09:35` 或 `14:50-14:59`。

### 相关文件

- `quant_backend/trade/views.py`
- `quant_backend/trade/models.py`
- `quant_backend/trade/engine.py`
- `quant_backend/trade/executor.py`
- `quant_backend/trade/urls.py`
- `quant_frontend/src/components/TradePanel.vue`
- `quant_frontend/src/components/MyStrategies.vue`

### 可验证命令

```powershell
cd quant_backend
python manage.py shell -c "from users.models import UserProfile; print(list(UserProfile.objects.values('user__username','balance','last_total_assets')[:10]))"
python manage.py shell -c "from trade.models import Position,Order; print('positions', list(Position.objects.values('user__username','stock_code','volume','avg_price')[:20])); print('orders', list(Order.objects.order_by('-order_time').values('user__username','stock_code','direction','price','volume','status','order_time')[:10]))"
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/api/trade/positions/
```

## 7. 资产/收益不一致

### 现象

顶部资产卡片、持仓市值、日内收益曲线、日线收益曲线或订单推算结果不一致。

### 高概率原因

- `UserInfoView` 每次读取会调用 `UserProfile.update_asset_cache()`，顶部卡片是实时缓存刷新后的值。
- `PerformanceView?type=intraday` 用当日订单、当前持仓和分钟线倒推，并把最后一点强制缝合到 `profile.last_total_assets`。
- `PerformanceView?type=daily` 主要来自 `DailyPerformance` 表，若今天没有记录会临时计算今日数据。
- `PositionListView` 会调用 `sync_positions()`，按 `filled` 订单重建持仓，可能与直接修改的持仓表不一致。
- 当前价格优先级不同：有些逻辑优先分钟线，有些在 15:00 后优先当日日线。

### 排查步骤

1. 先调用 `/api/users/info/` 触发一次资产缓存刷新。
2. 对比 `UserProfile`、`Position`、`Order`、`DailyPerformance` 四类数据。
3. 检查模拟时间对应日期是否有分钟线，否则日内收益接口可能返回空数组。
4. 如果持仓异常，先理解 `sync_positions()` 从订单重算的结果，不要直接改表。
5. 若日线收益不一致，重点检查 `DailyPerformance` 是否有上一交易日记录。

### 相关文件

- `quant_backend/users/views.py`
- `quant_backend/users/models.py`
- `quant_backend/trade/views.py`
- `quant_backend/trade/tasks.py`
- `quant_backend/trade/models.py`
- `quant_frontend/src/components/AssetOverview.vue`
- `quant_frontend/src/components/PerformanceChart.vue`
- `quant_frontend/src/components/IntradayPerformanceChart.vue`
- `quant_frontend/src/components/DailyPerformanceChart.vue`
- `quant_frontend/src/components/PositionList.vue`

### 可验证命令

```powershell
cd quant_backend
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/api/users/info/
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/trade/api/performance/?type=intraday
curl.exe -i -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/trade/api/performance/?type=daily
python manage.py shell -c "from users.models import UserProfile; from trade.models import Position,Order,DailyPerformance; print('profiles', list(UserProfile.objects.values('user__username','balance','last_market_value','last_total_assets','daily_profit','total_profit')[:10])); print('positions', list(Position.objects.values('user__username','stock_code','volume','avg_price')[:20])); print('daily_perf', list(DailyPerformance.objects.order_by('-date').values('user__username','date','total_assets','day_profit','total_return_rate')[:10]))"
```

## 8. 回测模块报错

### 现象

前端回测提示“网络请求异常”“引擎回测失败”，后端返回 `500`，或报 PySpark、Java、Pandas、数据为空相关错误。

### 高概率原因

- 缺少 `pyspark`、`pandas`、`numpy`，或 Java 环境不可用。
- 回测区间内 `StockData` 没有日线数据，`load_data()` 会抛出 `在 ... 期间没有股票数据！`。
- 系统没有任何用户，`RunBacktestView` 会返回“系统无用户，请先创建管理员”。
- `top_n`、`weight_mom`、`weight_bias`、日期格式或初始资金参数异常。
- Spark 本地模式需要绑定 `127.0.0.1`，被安全软件或端口占用影响时会初始化失败。

### 排查步骤

1. 先检查 Python 依赖和 Java 是否可用。
2. 确认回测日期区间内 `StockData` 有足够数据。
3. 确认至少存在一个 Django 用户。
4. 用只读 shell 调用 `SparkBacktestEngine.load_data()` 验证数据和 Spark 初始化。
5. 前端报网络异常时，优先看后端控制台 traceback。

### 相关文件

- `quant_backend/backtest/views.py`
- `quant_backend/backtest/engine.py`
- `quant_backend/backtest/models.py`
- `quant_backend/backtest/urls.py`
- `quant_frontend/src/views/BacktestView.vue`
- `quant_backend/stocks/models.py`

### 可验证命令

```powershell
cd quant_backend
python -c "import importlib.util; mods=['pyspark','pandas','numpy','django']; print({m: importlib.util.find_spec(m) is not None for m in mods})"
java -version
python manage.py shell -c "from django.contrib.auth.models import User; from stocks.models import StockData; print('users', User.objects.count()); print('rows_2025', StockData.objects.filter(date__gte='2025-01-01', date__lte='2025-12-31').count())"
python manage.py shell -c "from backtest.engine import SparkBacktestEngine; e=SparkBacktestEngine(task_id='check'); sdf=e.load_data('2025-01-01','2025-12-31'); print('spark rows', sdf.count()); e.stop()"
```

## 9. 数据库连接失败

### 现象

后端命令或接口报 `OperationalError`、`Access denied`、`Unknown database 'quant_db'`、`Can't connect to MySQL server`，或 `get_mock_now()` 返回真实时间而不是数据库模拟时间。

### 高概率原因

- MySQL 服务未启动，或 `127.0.0.1:3306` 不可达。
- `settings.py` 中数据库名、用户名、密码和本地 MySQL 不一致。
- Python MySQL 驱动缺失，Django MySQL 后端通常需要 `mysqlclient` 对应的 `MySQLdb`。
- 数据库存在但未迁移，导致表不存在。
- `get_mock_now()` 捕获异常后回退到 `timezone.now()`，让上层看起来还能运行，但行情时间和资产会不可信。

### 排查步骤

1. 用 TCP 检查 `3306` 端口连通性。
2. 用 Django `connection.ensure_connection()` 验证实际配置能否连上。
3. 检查 MySQL 驱动是否安装。
4. 检查迁移状态和关键表数据。
5. 如果数据库不可用，不要据此修改行情或时间逻辑，先恢复连接。

### 相关文件

- `quant_backend/quant_backend/settings.py`
- `quant_backend/trade/time_utils.py`
- `quant_backend/trade/models.py`
- `quant_backend/stocks/models.py`
- `quant_backend/users/models.py`
- `quant_backend/manage.py`

### 可验证命令

```powershell
cd quant_backend
Test-NetConnection 127.0.0.1 -Port 3306
python -c "import importlib.util; print('MySQLdb', importlib.util.find_spec('MySQLdb') is not None); print('pymysql', importlib.util.find_spec('pymysql') is not None)"
python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('connected to', connection.settings_dict['NAME'])"
python manage.py showmigrations
python manage.py shell -c "from trade.models import SystemSettings; from stocks.models import StockData; print('settings', SystemSettings.objects.count()); print('stock daily rows', StockData.objects.count())"
```

## 10. 依赖缺失问题

### 现象

后端报 `ModuleNotFoundError` 或 `ImportError`，前端报 `vite`、`vue`、`element-plus`、`echarts` 找不到，回测报 `pyspark` 找不到，或 README 中的 `pip install -r requirements.txt` 无法执行。

### 高概率原因

- 仓库当前未发现 `quant_backend/requirements.txt`、`requirements*.txt` 或 `pyproject.toml`。
- 后端依赖需要从源码 import 反推：Django、DRF、authtoken、django-cors-headers、django-apscheduler、mysqlclient/MySQLdb、pandas、numpy、pyspark 等。
- 前端依赖由 `quant_frontend/package.json` 管理，当前依赖包括 `axios`、`echarts`、`element-plus`、`pinia`、`vue`、`vue-router`、`vite`。
- `quant_backend/package.json` 存在前端类依赖，但后端实际是 Django 项目，不能用它替代 Python 依赖管理。
- Python 版本、Java 版本或虚拟环境不匹配。

### 排查步骤

1. 先确认当前 Python、Node、npm、Java 版本。
2. 检查后端关键 Python 模块是否可发现。
3. 检查前端 `node_modules` 和 `package-lock.json` 是否存在，再运行构建验证。
4. 如果缺 Python 依赖，优先补齐环境或生成依赖清单，不要改业务代码绕过 import。
5. 如果缺 Spark/Java，先用最小 import 和 `java -version` 验证。

### 相关文件

- `README.md`
- `quant_backend/manage.py`
- `quant_backend/package.json`
- `quant_frontend/package.json`
- `quant_frontend/package-lock.json`
- `quant_backend/backtest/engine.py`
- `quant_backend/quant_backend/settings.py`

### 可验证命令

```powershell
python --version
node --version
npm --version
java -version
cd quant_backend
python -c "import importlib.util; mods=['django','rest_framework','corsheaders','django_apscheduler','MySQLdb','pandas','numpy','pyspark']; print({m: importlib.util.find_spec(m) is not None for m in mods})"
python manage.py check
cd ..\quant_frontend
npm run build
```
