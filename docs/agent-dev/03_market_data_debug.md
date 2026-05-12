# 行情数据调试文档

本文只覆盖股票行情、大盘指数、日线/分钟线数据链路，目标是帮助后续 agent 快速定位行情展示问题。

## 核心结论

- 后端行情入口统一在 `quant_backend/stocks/urls.py`，挂载到项目根路由 `stocks/` 下，完整路径是 `/stocks/api/...`，来源见 `quant_backend/quant_backend/urls.py`。
- 行情展示时间不是服务器真实时间，而是 `trade.time_utils.get_mock_now()` 返回的 `SystemSettings.current_mock_time`，来源见 `quant_backend/trade/time_utils.py` 和 `quant_backend/trade/models.py`。
- 股票日线与指数日线都按模拟日期过滤：`date__lte=mock_date`，不会展示模拟日期之后的日线，来源见 `quant_backend/stocks/views.py`。
- 股票分钟线默认不是只查当天，而是取模拟时间之前最近 500 根 5 分钟 K 线；代码先宽松查询到 `mock_naive + 1 day`，再在内存中用 `item_naive <= mock_naive` 严格过滤未来数据，来源见 `quant_backend/stocks/views.py`。
- 大盘指数分钟线直接按 `MarketIndexMinuteData.date__lte=mock_query_time` 查询，没有股票分钟线那段内存二次过滤，来源见 `quant_backend/stocks/views.py`。
- 前端行情页全部直接请求 `http://127.0.0.1:8000/` 下的接口，不使用统一 API 客户端，来源见 `quant_frontend/src/views/MarketView.vue`、`quant_frontend/src/views/StockDetailView.vue`、`quant_frontend/src/views/MarketIndexDetailView.vue`、`quant_frontend/src/components/MarketIndexBoard.vue`。
- 当前 Django `TIME_ZONE = "UTC"` 且 `USE_TZ = True`，时区转换会影响分钟线与模拟时间比较，来源见 `quant_backend/quant_backend/settings.py`。

## 数据模型

### 股票行情模型

源码：`quant_backend/stocks/models.py`

`StockData`

- 用途：股票日线数据，用于日 K、历史涨跌幅、分钟线昨收兜底。
- 表名：`stock_data_daily`。
- 关键字段：`code`、`date`、`open`、`high`、`low`、`close`、`volume`、`amount`。
- 时间字段：`date = DateField`，只有交易日期。
- 索引：`code + date`。

`StockMinuteData`

- 用途：股票 5 分钟线，用于股票详情分时图、市场列表最新价、持仓市值、资产曲线。
- 表名：`stock_data_minute`。
- 关键字段：`code`、`date`、`open`、`high`、`low`、`close`、`volume`、`amount`。
- 时间字段：`date = DateTimeField`，包含交易时间。
- 索引：`code + date`。

`StockBasicInfo`

- 用途：股票代码与名称字典，是行情列表分页的主表。
- 表名：Django 默认表名，未显式指定 `db_table`。
- 关键字段：`code` 唯一、`name`。

### 大盘指数模型

源码：`quant_backend/stocks/models.py`

`MarketIndexBasicInfo`

- 用途：指数代码、名称、交易所字典。
- 表名：`market_index_basic`。
- 关键字段：`code` 唯一、`name`、`market`。

`MarketIndexDailyData`

- 用途：指数日线，用于大盘指数卡片和指数详情日 K。
- 表名：`market_index_daily`。
- 关键字段：`code`、`date`、`open`、`high`、`low`、`close`、`volume`、`amount`、`amplitude`、`change_pct`、`change_amount`、`turnover_rate`、`source`。
- 时间字段：`date = DateField`。
- 索引：`code + date`。
- 唯一约束：`code + date`，约束名 `uniq_market_index_daily`。

`MarketIndexMinuteData`

- 用途：指数 5 分钟线，用于指数详情分时图。
- 表名：`market_index_minute`。
- 关键字段：`code`、`date`、`open`、`high`、`low`、`close`、`volume`、`amount`、`source`。
- 时间字段：`date = DateTimeField`。
- 索引：`code + date`。
- 唯一约束：`code + date`，约束名 `uniq_market_index_minute`。

## 后端接口与查询逻辑

### 路由总览

源码：`quant_backend/stocks/urls.py`、`quant_backend/quant_backend/urls.py`

| 前端请求 | 后端视图 | 用途 |
| --- | --- | --- |
| `GET /stocks/api/indices/` | `get_market_index_list_api` | 大盘指数概览卡片 |
| `GET /stocks/api/index/<index_code>/?freq=min&limit=1200` | `get_market_index_data_api` | 指数 5 分钟线 |
| `GET /stocks/api/index/<index_code>/?freq=daily&limit=1200` | `get_market_index_data_api` | 指数日 K |
| `GET /stocks/api/data/<stock_code>/?freq=min` | `get_stock_data_api` | 股票分时/5 分钟线 |
| `GET /stocks/api/data/<stock_code>/?freq=daily` | `get_stock_data_api` | 股票日 K |
| `GET /stocks/api/data/<stock_code>/?freq=min&date=YYYY-MM-DD` | `get_stock_data_api` | 指定日期股票分钟线回看 |
| `GET /stocks/api/market/?page=1&sort_prop=...&sort_order=...` | `get_market_list_api` | 全市场行情列表 |

### 大盘指数概览

源码：`quant_backend/stocks/views.py`

- 入口：`get_market_index_list_api`。
- 当前时间：通过 `get_mock_clock()` 间接调用 `get_mock_now()`。
- 查询主表：`MarketIndexBasicInfo.objects.all()`。
- 排序：`INDEX_ORDER = ['sh.000001', 'sz.399001', 'sz.399006', 'sh.000300']` 优先。
- 最新点位：`MarketIndexDailyData.objects.filter(code=info.code, date__lte=mock_date).order_by('-date').first()`。
- 涨跌幅：优先使用 `latest.change_pct`；为空时用最新收盘和上一交易日收盘计算。
- 返回字段：`code`、`name`、`market`、`price`、`change`、`change_amount`、`date`、`volume`、`amount`、`current_mock_time`。

### 指数 K 线详情

源码：`quant_backend/stocks/views.py`

- 入口：`get_market_index_data_api`。
- 指数名称：从 `MarketIndexBasicInfo` 查 `name`，不存在显示 `未知指数`。
- `freq in ['min', '5min']`：查询 `MarketIndexMinuteData.objects.filter(code=index_code, date__lte=mock_query_time).order_by('-date')[:limit]`。
- 其他 `freq`：查询 `MarketIndexDailyData.objects.filter(code=index_code, date__lte=mock_date).order_by('-date')[:limit]`，并把 `freq` 归一为 `daily`。
- 查询结果倒序取出后再 `reversed`，最终返回旧到新，前端图表按数组顺序渲染。
- 返回字段：`name`、`index_code`、`freq`、`latest_price`、`latest_time`、`current_mock_time`、`data`。

### 股票 K 线详情

源码：`quant_backend/stocks/views.py`

- 入口：`get_stock_data_api`。
- 股票名称：从 `StockBasicInfo` 查 `name`，不存在显示 `未知股票`。
- 当前时间：直接调用 `get_mock_now()`，再转成 naive 时间 `mock_naive`。
- 分钟线默认模式：`freq=min` 且没有 `date` 参数。
- 分钟线默认模式查询：先用 `StockMinuteData.objects.filter(code=stock_code, date__lte=query_limit_date).order_by('-date')[:1000]`，其中 `query_limit_date = mock_naive + timedelta(days=1)`。
- 分钟线默认模式防未来数据：遍历候选数据，把每条 `item.date` 转 naive 后只保留 `item_naive <= mock_naive`，最多保留 500 根。
- 分钟线默认模式昨收：取返回列表第一根分钟线日期之前最近一条 `StockData` 作为 `pre_close`。
- 分钟线指定日期回看：`date__contains=target_date_str` 查询当天全部分钟线，没有按 `get_mock_now()` 限制。
- 日线模式：`StockData.objects.filter(code=stock_code, date__lte=mock_date).order_by('-date')[:500]`。
- 返回字段：`name`、`stock_code`、`freq`、`target_date`、`pre_close`、`current_mock_time`、`data`。

### 全市场行情列表

源码：`quant_backend/stocks/views.py`

- 入口：`get_market_list_api`。
- 分页：`StandardResultsSetPagination`，默认 `page_size = 20`，最大 100。
- 股票全集：从 `StockBasicInfo.objects.all()` 分页，列表里没有 `StockBasicInfo` 的股票不会显示。
- 数据库排序字段：仅 `code`、`name` 直接在 DB 排序；`price`、`change` 等计算字段在当前页内排序。
- 最新价优先级：先找模拟时间之前最近的 `StockMinuteData`，找不到再用模拟日期之前最近的 `StockData`。
- 分钟线候选查询：`StockMinuteData.objects.filter(code=stock.code, date__lte=mock_now + timedelta(days=1)).order_by('-date')[:50]`。
- 分钟线防未来数据：遍历候选数据，把 `cand.date` 转 naive 后要求 `cand_naive <= mock_naive`。
- 日线兜底：`StockData.objects.filter(code=stock.code, date__lte=mock_today).order_by('-date').first()`。
- 区间涨跌幅基准：通过 `get_historical_close()` 查 `mock_today - 7/365/730/1095 days` 之前最近收盘价。

## 模拟时间机制

### 时间来源

源码：`quant_backend/trade/time_utils.py`、`quant_backend/trade/models.py`

- `get_mock_now()` 从 `SystemSettings.objects.first()` 读取 `current_mock_time`。
- 如果没有 `SystemSettings` 记录，会创建一条默认记录，时间为 `timezone.now()`。
- 如果数据库未就绪或异常，会兜底返回 `timezone.now()`。
- `SystemSettings` 表名是 `system_settings`，字段包括 `current_mock_time`、`time_speed`、`last_update_time`。

### 时间推进

源码：`quant_backend/trade/tasks.py`

- `clock_tick()` 每次读取 `SystemSettings.current_mock_time`，按 `time_speed` 秒递增。
- 每跨过 5 分钟触发 `record_intraday_snapshot(new_time)`。
- 从 15:00 前跨到 15:00 后，触发 `record_daily_performance()`。
- 当前实现不跳过休市时间，注释明确“移除了 skip_non_trading 的判断逻辑”。

### 手动设置时间

源码：`quant_backend/trade/views.py`、`quant_backend/trade/urls.py`

- 系统时间读取接口：`GET /trade/api/time/` 或 `GET /api/trade/time/`，视图是 `SystemTimeView`。
- 控制接口：`POST /trade/api/control/` 或 `POST /api/trade/control/`，视图是 `SystemControlView`。
- `action=set_speed` 修改 `time_speed`。
- `action=set_time` 修改 `current_mock_time`，如果只传日期，会补 `09:30:00`。
- `set_time` 保存后会调用 `settings.hard_reset_world()`，会清空订单、持仓、收益快照并重置用户资产，源码见 `quant_backend/trade/models.py`。

### `date__lte` 与展示边界

源码：`quant_backend/stocks/views.py`

- 股票日线：只显示 `StockData.date <= mock_date`。
- 指数日线：只显示 `MarketIndexDailyData.date <= mock_date`。
- 指数分钟线：只显示 `MarketIndexMinuteData.date <= mock_query_time`。
- 股票分钟线：数据库查询条件故意宽到 `mock_naive + 1 day`，但最终展示必须通过 `item_naive <= mock_naive`。
- 全市场列表：分钟候选也宽到 `mock_now + 1 day`，但最终 `last_min` 必须满足 `cand_naive <= mock_naive`。
- 自选股行情：`UserFavoriteSerializer._get_market_snapshot()` 复刻全市场逻辑，源码见 `quant_backend/users/serializers.py`。

## 前后端对应关系

### 行情中心列表

源码：`quant_frontend/src/views/MarketView.vue`、`quant_frontend/src/components/MarketHeader.vue`、`quant_frontend/src/components/StockTable.vue`

- 页面路由：`/market`，来源见 `quant_frontend/src/router/index.js`。
- 首次加载：`MarketView.onMounted()` 调用 `fetchMarketData(1)`。
- 轮询：每 3 秒刷新一次；全市场走 `fetchMarketData`，自选股走 `fetchFavoritesList`。
- 后端接口：`stocks/api/market/?page=${page}`。
- 排序参数：`sort_prop`、`sort_order`。
- 表格字段：`code`、`name`、`price`、`change`。
- 点击股票名称：`StockTable.goToDetail()` 跳转 `/stock/${code}`。

### 大盘指数卡片

源码：`quant_frontend/src/components/MarketIndexBoard.vue`

- 页面位置：`MarketView` 顶部。
- 后端接口：`stocks/api/indices/`。
- 展示字段：`name`、`code`、`price`、`change`、`change_amount`、`amount`。
- `latestDate` 取 `indices[0]?.date`，因此卡片顶部“截至”只看第一个指数的日期。
- 点击指数卡片：跳转 `/index/${code}`。

### 股票详情页

源码：`quant_frontend/src/views/StockDetailView.vue`、`quant_frontend/src/components/StockHeader.vue`、`quant_frontend/src/components/StockChart.vue`、`quant_frontend/src/components/StockMinuteChart.vue`、`quant_frontend/src/components/StockDailyChart.vue`

- 页面路由：`/stock/:code`。
- 默认模式：`viewMode = 'min'`。
- 行情报价：`fetchQuote()` 固定请求 `stocks/api/data/${stockCode}/?freq=min`，取最后一根的 `close` 作为 `latestPrice`。
- 图表数据：`fetchChartData()` 请求 `stocks/api/data/${stockCode}/?freq=${viewMode}`。
- 轮询：每 2 秒刷新报价；只有 `viewMode === 'min'` 时轮询图表。
- 图表组件路由：`StockChart` 根据 `freq` 分发到 `StockMinuteChart` 或 `StockDailyChart`。
- 空数据表现：分钟图和日 K 图都会显示 `暂无数据`。

### 指数详情页

源码：`quant_frontend/src/views/MarketIndexDetailView.vue`、`quant_frontend/src/components/StockChart.vue`

- 页面路由：`/index/:code`。
- 默认模式：`viewMode = 'min'`。
- 后端接口：`stocks/api/index/${indexCode}/?freq=${viewMode}&limit=${limit}`。
- `limit` 固定 1200。
- 轮询：每 10 秒刷新一次，但仅在分钟模式下刷新。
- 图表复用 `StockChart`，因此指数数据字段必须兼容股票 K 线字段。

## 数据导入与下载脚本

### 股票小样本初始化

入口：`python manage.py init_minute_data`

源码：`quant_backend/stocks/management/commands/init_minute_data.py`

- 目标股票：硬编码 5 只股票，包含寒武纪、中际旭创、胜宏科技、新易盛、天孚通信。
- 数据源：AkShare。
- 功能：清空 `StockData`、`StockMinuteData`、`StockBasicInfo`，重建股票基础信息，下载最近 3 年日线和 5 分钟线。
- 分钟线时间：用 `make_aware()` 写入带时区时间。
- 风险：会清空旧股票行情数据。

### 股票小样本重置与补分钟线

入口：`python manage.py fill_mock_data`

源码：`quant_backend/stocks/management/commands/fill_mock_data.py`

- 目标股票：同样硬编码 5 只股票。
- 数据源：AkShare。
- 功能：清空股票行情和基础信息，下载日线和尽可能多的真实分钟线；若某个日线交易日没有分钟线，则用模拟算法生成 48 根 5 分钟 K 线。
- 模拟分钟时间：上午从 09:35 开始 24 根，下午从 13:05 开始 24 根。
- 风险：会清空旧股票行情数据，并生成非真实分钟线。

### 股票真实 5 分钟线修复

入口：`python manage.py download_real_3y`

源码：`quant_backend/stocks/management/commands/download_real_3y.py`

- 目标股票：硬编码 5 只股票。
- 数据源：Baostock。
- 功能：清空 `StockMinuteData`，下载最近 5 年 5 分钟线。
- 注意：只清空和写入分钟线，不重建 `StockData` 和 `StockBasicInfo`。
- 风险：会清空全部股票分钟线。

### 沪深300批量同步

入口：`python quant_backend/download_hs300_to_db.py [参数]`

源码：`quant_backend/download_hs300_to_db.py`

- 数据源：Baostock。
- 功能：下载沪深300成分股基础信息、日线、5 分钟线到本地 CSV，再上传到数据库。
- 本地缓存目录：`raw_data/hs300_cache`。
- 状态文件：`raw_data/hs300_cache/state.json`。
- 默认日线开始日期：`2018-01-01`。
- 默认 5 分钟线开始日期：`2024-01-01`。
- 常用参数：`--daily-start`、`--minute-start`、`--end`、`--force-download`、`--force-upload`、`--skip-download`、`--skip-upload`。
- 上传策略：基础信息逐个 `update_or_create`；日线和分钟线按 code + 日期范围先删后插。
- 风险：`--force-upload` 会按范围删除再插入行情数据。

### 大盘指数数据下载

入口：`python manage.py download_market_index_data [参数]`

源码：`quant_backend/stocks/management/commands/download_market_index_data.py`

- 目标指数：上证指数 `sh.000001`、深证成指 `sz.399001`、创业板指 `sz.399006`、沪深300 `sh.000300`。
- 基础信息：写入 `MarketIndexBasicInfo`。
- 日线数据源：优先 AkShare，空数据时用 pytdx 兜底。
- 分钟线数据源：pytdx 历史分钟数据，聚合为 5 分钟线。
- 默认范围：`--start 2022-01-01` 到今天。
- 常用参数：`--start`、`--end`、`--codes`、`--skip-daily`、`--skip-minute`、`--force`、`--batch-size`、`--sleep`。
- 分钟线交易时间：按 09:31-11:30、13:01-15:00 的 1 分钟数据聚合，每 5 条生成一根，时间取 chunk 最后一条。
- 风险：`--force` 会删除指定范围内已有指数日线或当天分钟线后重建。

## 常见问题排查

### 1. 股票详情页显示未来分钟线

可能原因：

- `StockMinuteData.date` 的时区与 `SystemSettings.current_mock_time` 不一致，导致 `timezone.make_naive()` 后比较结果偏移。
- 导入脚本写入了 naive datetime，而 Django 在 `USE_TZ=True` 下按 UTC 保存或转换。
- 后端默认分钟线查询先宽查到 `mock_naive + 1 day`，如果内存过滤被改坏，会直接暴露未来数据。
- 前端图表拿到的是旧请求返回的数据，新请求被慢响应覆盖的可能性较低，但需要检查轮询和请求时序。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_stock_data_api` 中 `item_naive <= mock_naive` 是否仍存在。
- `quant_backend/trade/time_utils.py`：确认 `get_mock_now()` 返回值。
- `quant_backend/trade/models.py`：检查 `SystemSettings.current_mock_time`。
- `quant_backend/quant_backend/settings.py`：确认 `TIME_ZONE`、`USE_TZ`。
- `quant_backend/stocks/management/commands/init_minute_data.py`：检查 `make_aware()` 写入。
- `quant_backend/stocks/management/commands/fill_mock_data.py`：检查模拟分钟线时间生成。
- `quant_frontend/src/views/StockDetailView.vue`：确认请求参数是 `freq=min`。
- `quant_frontend/src/components/StockMinuteChart.vue`：确认图表直接按后端数组渲染，没有二次过滤。

### 2. 股票详情页只显示旧日期，不显示当前模拟日期

可能原因：

- 当前模拟日期没有 `StockMinuteData`，默认分钟线会退到模拟时间之前最近 500 根，因此可能跨天显示旧数据。
- 当前模拟日期没有 `StockData`，日 K 会停在 `date__lte=mock_date` 的最近交易日。
- `StockBasicInfo.code` 与行情表 `code` 不一致，例如一个是 `sh.600000`，另一个是 `600000`。
- 模拟时间被设置到非交易日或盘前，分钟线本来就没有当天数据。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_stock_data_api` 默认分钟线“最近 500 根”逻辑和日线 `date__lte=mock_date`。
- `quant_backend/stocks/models.py`：确认 `StockData.code`、`StockMinuteData.code`、`StockBasicInfo.code` 字段含义一致。
- `quant_backend/trade/views.py`：检查 `SystemControlView` 设置的模拟时间。
- `quant_backend/stocks/management/commands/init_minute_data.py`：确认下载范围是否覆盖当前模拟日期。
- `quant_backend/download_hs300_to_db.py`：确认 `--minute-start`、`--end` 是否覆盖当前模拟日期。

### 3. 股票分钟线为空

可能原因：

- `StockMinuteData` 表没有该股票数据。
- 请求的 `stock_code` 不匹配数据库中的 `code`。
- 模拟时间早于该股票最早一根分钟线。
- 指定 `date=YYYY-MM-DD` 回看时，该日期没有分钟线；该模式使用 `date__contains=target_date_str`，不会跨天兜底。
- 分钟线导入脚本失败或被 `download_real_3y` 清空后未成功重建。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_stock_data_api` 分钟线两种模式。
- `quant_backend/stocks/models.py`：确认 `StockMinuteData` 表结构和 code 字段。
- `quant_backend/stocks/management/commands/init_minute_data.py`：确认 AkShare 分钟线下载与入库。
- `quant_backend/stocks/management/commands/download_real_3y.py`：确认是否清空了分钟线。
- `quant_backend/download_hs300_to_db.py`：确认 5 分钟线下载和上传阶段。
- `quant_frontend/src/views/StockDetailView.vue`：确认前端请求的是 `stocks/api/data/${stockCode}/?freq=${viewMode}`。
- `quant_frontend/src/components/StockMinuteChart.vue`：空数组会显示 `暂无数据`。

### 4. 股票日 K 为空

可能原因：

- `StockData` 表没有该股票日线。
- 模拟日期早于该股票最早日线，`date__lte=mock_date` 查不到数据。
- `stock_code` 格式不一致。
- 数据导入脚本只导入了分钟线，例如只执行 `download_real_3y`，没有导入日线。

排查文件：

- `quant_backend/stocks/views.py`：检查 `StockData.objects.filter(code=stock_code, date__lte=mock_date)`。
- `quant_backend/stocks/models.py`：确认 `StockData` 表名 `stock_data_daily`。
- `quant_backend/stocks/management/commands/init_minute_data.py`：确认日线下载。
- `quant_backend/stocks/management/commands/fill_mock_data.py`：确认日线下载和清空逻辑。
- `quant_backend/download_hs300_to_db.py`：确认 `upload_daily_files()` 是否执行。
- `quant_frontend/src/components/StockDailyChart.vue`：空数组会显示 `暂无数据`。

### 5. 全市场行情列表没有某只股票

可能原因：

- 行情列表以 `StockBasicInfo` 为主表分页；没有基础信息就不会出现在列表中。
- 分页只显示当前页，目标股票在其他页。
- 排序只对当前页计算字段排序，按涨跌幅等排序时不是全市场全量排序。
- 自选股列表走 `api/users/favorites/`，不是 `stocks/api/market/`。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_market_list_api` 使用 `StockBasicInfo.objects.all()`。
- `quant_backend/stocks/models.py`：确认 `StockBasicInfo.code` 唯一。
- `quant_backend/users/serializers.py`：检查自选股价格快照逻辑。
- `quant_frontend/src/views/MarketView.vue`：检查全市场和自选股 tab 分支。
- `quant_frontend/src/components/StockTable.vue`：检查分页和跳转逻辑。

### 6. 全市场列表价格为 0 或涨跌幅为 0

可能原因：

- `StockMinuteData` 和 `StockData` 都没有该股票在模拟时间之前的数据。
- 有最新价但没有上一交易日日线，`prev_close = 0`，`calc_change()` 返回 0。
- 股票代码匹配失败。
- 模拟时间早于所有行情数据。

排查文件：

- `quant_backend/stocks/views.py`：检查 `last_min`、`last_day`、`prev_day_orig`、`prev_day` 查询。
- `quant_backend/users/serializers.py`：自选股同类问题检查 `_get_market_snapshot()`。
- `quant_backend/stocks/models.py`：检查 `StockData`、`StockMinuteData`、`StockBasicInfo`。
- `quant_frontend/src/views/MarketView.vue`：确认 `tableData` 来自 `res.data.results`。

### 7. 大盘指数卡片为空或价格为 0

可能原因：

- `MarketIndexBasicInfo` 没有基础信息。
- `MarketIndexDailyData` 没有模拟日期之前的数据。
- 只下载了分钟线或下载脚本失败，日线为空。
- 模拟时间早于指数日线起始日期。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_market_index_list_api`。
- `quant_backend/stocks/models.py`：检查 `MarketIndexBasicInfo`、`MarketIndexDailyData`。
- `quant_backend/stocks/management/commands/download_market_index_data.py`：确认 `upsert_basic_info()` 和 `download_daily()`。
- `quant_frontend/src/components/MarketIndexBoard.vue`：确认请求 `stocks/api/indices/`。

### 8. 指数详情分钟线为空

可能原因：

- `MarketIndexMinuteData` 没有该指数数据。
- 只执行了 `download_market_index_data --skip-minute`。
- pytdx 分钟接口失败，脚本统计中 `failed` 交易日较多。
- 模拟时间早于最早指数分钟线。
- 前端传 `freq=min`，后端支持 `min` 和 `5min`；如果未来改成别的值，会落到日线分支。

排查文件：

- `quant_backend/stocks/views.py`：检查 `get_market_index_data_api` 的 `freq in ['min', '5min']` 分支。
- `quant_backend/stocks/models.py`：检查 `MarketIndexMinuteData`。
- `quant_backend/stocks/management/commands/download_market_index_data.py`：检查 `download_minute()`、`aggregate_to_5min()`。
- `quant_frontend/src/views/MarketIndexDetailView.vue`：确认请求 `freq=${viewMode}` 且默认 `viewMode='min'`。

### 9. 指数详情日 K 为空

可能原因：

- `MarketIndexDailyData` 没有该指数数据。
- 只执行了 `download_market_index_data --skip-daily`，且历史日线不存在。
- `index_code` 不在脚本预设或数据库基础信息中。
- 模拟日期早于指数日线起始日期。

排查文件：

- `quant_backend/stocks/views.py`：检查 `MarketIndexDailyData.objects.filter(code=index_code, date__lte=mock_date)`。
- `quant_backend/stocks/models.py`：检查 `MarketIndexDailyData` 唯一约束和字段。
- `quant_backend/stocks/management/commands/download_market_index_data.py`：检查 `MARKET_INDICES` 和 `download_daily()`。
- `quant_frontend/src/views/MarketIndexDetailView.vue`：确认 `viewMode='daily'` 时请求仍带 `limit=1200`。

### 10. 大盘指数卡片“截至日期”看起来不对

可能原因：

- 前端 `latestDate` 只取 `indices[0]?.date`，不是所有指数日期的最大值或最小值。
- 后端按 `INDEX_ORDER` 排序，第一个通常是上证指数，因此“截至”代表第一个指数。
- 不同指数下载覆盖日期不同。

排查文件：

- `quant_frontend/src/components/MarketIndexBoard.vue`：检查 `latestDate = computed(() => indices.value[0]?.date || '')`。
- `quant_backend/stocks/views.py`：检查 `INDEX_ORDER` 和每个指数独立查询 `latest`。
- `quant_backend/stocks/management/commands/download_market_index_data.py`：检查各指数数据量 summary。

### 11. 设置模拟时间后行情仍不变化

可能原因：

- 前端页面轮询间隔未到，或者当前在日 K 模式，股票详情日 K 不自动轮询。
- `SystemControlView.set_time` 写入失败。
- `get_mock_now()` 读取的是 `SystemSettings.objects.first()`，而手动修改了非第一条记录。
- `clock_tick()` 仍在后台推进时间，刚设置的时间又被流速推进。

排查文件：

- `quant_backend/trade/time_utils.py`：检查 `SystemSettings.objects.first()`。
- `quant_backend/trade/views.py`：检查 `SystemControlView`、`SystemTimeView`。
- `quant_backend/trade/tasks.py`：检查 `clock_tick()`。
- `quant_frontend/src/views/MarketView.vue`：全市场每 3 秒轮询。
- `quant_frontend/src/views/StockDetailView.vue`：股票详情每 2 秒刷新报价，分钟图才轮询。
- `quant_frontend/src/views/MarketIndexDetailView.vue`：指数分钟图每 10 秒轮询。

### 12. 控制台读取系统控制接口报错 `skip_non_trading`

可能原因：

- `SystemControlView.get()` 返回 `settings.skip_non_trading`，但 `SystemSettings` 模型已删除该字段。
- 行情接口本身不依赖 `skip_non_trading`，但控制台页面或调试请求可能失败。

排查文件：

- `quant_backend/trade/views.py`：检查 `SystemControlView.get()`。
- `quant_backend/trade/models.py`：确认 `SystemSettings` 字段。
- `quant_backend/trade/tasks.py`：注释说明已移除跳过休市逻辑。

### 13. 分钟线时间整体偏移几个小时

可能原因：

- Django 配置 `TIME_ZONE = "UTC"`，但行情数据源是中国交易时间。
- 导入脚本有的写 aware datetime，有的写 naive datetime；在 `USE_TZ=True` 下数据库保存和读取会转换。
- 后端比较时混用了 aware 和 naive，通过 `timezone.make_naive()` 转换后可能与预期本地时间不一致。

排查文件：

- `quant_backend/quant_backend/settings.py`：检查 `TIME_ZONE`、`USE_TZ`。
- `quant_backend/stocks/views.py`：检查 `get_mock_clock()` 和 `get_stock_data_api` 的 `timezone.make_naive()`。
- `quant_backend/stocks/management/commands/init_minute_data.py`：使用 `make_aware()`。
- `quant_backend/stocks/management/commands/fill_mock_data.py`：使用 `timezone.make_aware()` 生成 day_start。
- `quant_backend/download_hs300_to_db.py`：上传分钟线时 `date=row["datetime"].to_pydatetime()`。

### 14. 自选股行情和全市场行情不一致

可能原因：

- 自选股接口走 `UserFavoriteSerializer._get_market_snapshot()`，它复制了全市场价格逻辑，但维护时可能只改了 `get_market_list_api` 没改这里。
- 自选股行的 `date` 使用收藏添加时间 `add_time`，不是行情时间。
- 全市场排序、分页只影响当前页，自选股是收藏列表本地排序。

排查文件：

- `quant_backend/users/serializers.py`：检查 `_get_market_snapshot()`。
- `quant_backend/stocks/views.py`：对比 `get_market_list_api`。
- `quant_frontend/src/views/MarketView.vue`：检查 `fetchFavoritesList()` 映射字段。

### 15. 股票详情最新价和图表最后一根不一致

可能原因：

- `fetchQuote()` 和 `fetchChartData()` 是两个请求，轮询间隔内可能拿到不同模拟时间的数据。
- `fetchQuote()` 固定请求 `freq=min`，即使当前视图是日 K，也用分钟线最后一根作为 `latestPrice`。
- 如果分钟线为空，`latestPrice` 不会更新，但图表可能显示日 K。

排查文件：

- `quant_frontend/src/views/StockDetailView.vue`：检查 `fetchQuote()` 和 `fetchChartData()`。
- `quant_backend/stocks/views.py`：检查 `get_stock_data_api` 对 `freq=min` 和 `freq=daily` 的不同返回。
- `quant_frontend/src/components/StockChart.vue`：检查 `freq` 分发。

## 快速定位清单

- 先查模拟时间：`quant_backend/trade/time_utils.py`、`quant_backend/trade/models.py`、`quant_backend/trade/views.py`。
- 再查接口过滤：`quant_backend/stocks/views.py`。
- 股票列表问题查：`get_market_list_api`、`StockBasicInfo`、`StockMinuteData`、`StockData`。
- 股票详情问题查：`get_stock_data_api`、`StockDetailView.vue`、`StockMinuteChart.vue`、`StockDailyChart.vue`。
- 指数卡片问题查：`get_market_index_list_api`、`MarketIndexBoard.vue`、`download_market_index_data.py`。
- 指数详情问题查：`get_market_index_data_api`、`MarketIndexDetailView.vue`、`MarketIndexMinuteData`、`MarketIndexDailyData`。
- 数据缺失先确认导入脚本：股票看 `init_minute_data.py`、`fill_mock_data.py`、`download_real_3y.py`、`download_hs300_to_db.py`；指数看 `download_market_index_data.py`。
- 时区异常优先查：`quant_backend/quant_backend/settings.py`、导入脚本的 datetime 写入、视图里的 `timezone.make_naive()`。
