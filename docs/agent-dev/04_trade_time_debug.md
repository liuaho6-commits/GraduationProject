# 交易与模拟时间调试路线图

本文用于 agent 排查交易、资产、订单、持仓、收益统计与模拟时间问题。只记录代码现状与疑似风险点，不代表已修复。

## 1. 先确认模拟时间源

排查任何交易或行情问题前，先确认当前代码使用的是“模拟时间”还是机器真实时间。

关键文件：

- `quant_backend/trade/time_utils.py`
- `quant_backend/trade/models.py`
- `quant_backend/trade/tasks.py`
- `quant_backend/trade/scheduler.py`
- `quant_backend/trade/views.py`
- `quant_backend/trade/admin.py`

模拟时间主入口：

- `get_mock_now()`：从数据库 `SystemSettings.objects.first()` 读取 `current_mock_time`。
- `set_mock_now(dt)`：批量更新 `SystemSettings.current_mock_time`，当前代码中未发现业务主流程调用。
- `get_next_trading_time(current_time)`：目前直接返回传入时间，不再跳过休市。

读取路线：

1. 查看 `system_settings` 表是否有记录。
2. 如果没有记录，`get_mock_now()` 会创建一条默认记录，`current_mock_time=timezone.now()`，`time_speed=1.0`。
3. 如果数据库异常或应用未就绪，`get_mock_now()` 会兜底返回 `timezone.now()`。
4. 市场接口、交易接口、资产接口应优先经 `get_mock_now()` 或 `SystemSettings.current_mock_time` 获取时间。

设置路线：

1. 后台 API：`SystemControlView.post()` 位于 `quant_backend/trade/views.py`。
2. `action=set_speed`：修改 `SystemSettings.time_speed`。
3. `action=set_time`：解析 `target_time`，写入 `current_mock_time`，随后调用 `settings.hard_reset_world()`。
4. Django Admin：`TimeFlowSettingsAdmin` 只改 `time_speed`。
5. Django Admin：`TimeResetSettingsAdmin.save_model()` 保存 `current_mock_time` 后调用 `hard_reset_world()`。
6. 自动流动：`scheduler.py` 每秒触发 `clock_tick()`，`clock_tick()` 按 `time_speed` 秒推进 `current_mock_time`。

注意：`quant_backend/mock_time.json` 存在，但当前读取到的主流程未使用它。当前模拟时间以数据库 `system_settings.current_mock_time` 为准。

## 2. 理解时间设置模型

`SystemSettings` 位于 `quant_backend/trade/models.py`。

核心字段：

- `current_mock_time`：当前模拟时间，交易、行情、收益统计的主时间锚点。
- `time_speed`：每次 `clock_tick()` 推进的模拟秒数。`time_speed <= 0` 时心跳直接返回。
- `last_update_time`：`auto_now=True`，记录模型保存时间，是机器真实时间语义，不应作为交易时间。

核心方法：

- `get_settings()`：固定获取或创建 `id=1` 的设置记录。
- `hard_reset_world()`：删除全部 `Order`、`Position`、`DailyPerformance`、`IntradayPerformance`，并将所有 `UserProfile` 资金和收益缓存重置为默认 `200000.00`。

代理模型：

- `TimeFlowSettings(SystemSettings)`：proxy model，不建新表，用于安全修改时间流速。
- `TimeResetSettings(SystemSettings)`：proxy model，不建新表，用于时间穿越。Admin 保存后会触发 `hard_reset_world()`。

疑似风险点：

- `SystemControlView.get()` 仍返回 `settings.skip_non_trading`，但 `SystemSettings` 当前模型和迁移 `0005` 已移除该字段。访问该 GET 接口可能抛异常。
- `get_mock_now()` 使用 `SystemSettings.objects.first()`，而 `SystemSettings.get_settings()` 使用 `id=1`。如果表里有多条记录，读取和设置可能不是同一条。
- `set_mock_now(dt)` 使用 `SystemSettings.objects.update(...)`，会更新所有设置记录，不限 `id=1`。
- `get_mock_now()` 数据库异常时兜底到 `timezone.now()`，会让交易或行情临时退回真实时间。

## 3. 确认时间推进链路

自动推进路线：

1. `TradeConfig.ready()` 位于 `quant_backend/trade/apps.py`。
2. 当 `RUN_MAIN == 'true'` 时调用 `start_scheduler()`。
3. `start_scheduler()` 位于 `quant_backend/trade/scheduler.py`。
4. APScheduler 每秒执行一次 `trade.tasks.clock_tick`。
5. `clock_tick()` 读取第一条 `SystemSettings`。
6. `new_time = settings.current_mock_time + timedelta(seconds=settings.time_speed)`。
7. 如果跨过新的 5 分钟边界，调用 `record_intraday_snapshot(new_time)`。
8. 如果从 15:00 前跨到 15:00 后或跨日，调用 `record_daily_performance()`。
9. 使用 `SystemSettings.objects.filter(id=settings.id).update(current_mock_time=valid_time)` 写回时间。
10. 调用 `engine.run_all_active_strategies()` 执行策略撮合。

调试时间不动：

1. 查 `system_settings.time_speed` 是否 `<= 0`。
2. 查后端启动环境是否满足 `RUN_MAIN == 'true'`。
3. 查 `trade/scheduler.py` 是否成功打印时间调度器启动信息。
4. 查 `django_apscheduler` 相关表或日志是否有 `clock_tick` 执行错误。
5. 查 `clock_tick()` 是否因为 `SystemSettings.objects.first()` 返回空或异常提前退出。

疑似风险点：

- `quant_backend/trade/management/commands/run_scheduler.py` 引用 `run_active_strategies`、`record_intraday_assets`，但当前 `tasks.py` 中未定义这两个函数。
- `TradeConfig.start_scheduler()` 方法内部也引用 `run_active_strategies`、`record_intraday_assets`，但 `ready()` 当前实际调用的是 `scheduler.py` 的 `start_scheduler()`，这个旧方法未直接执行。
- `tasks.py` 导入了 `get_next_trading_time` 但未使用，当前时间线是线性流逝，不跳过周末或休市。

## 4. 下单到成交的排查路线

系统有两条主要交易路径：手动下单和策略自动下单。

手动下单入口：

- URL：`quant_backend/trade/urls.py` 中 `place_order/`
- View：`PlaceOrderView.post()` 位于 `quant_backend/trade/views.py`
- 模型：`Order`、`Position`、`UserProfile`

手动下单流程：

1. 调用 `sync_positions(user)`，用历史已成交订单重建 `Position.volume`。
2. 开启 `transaction.atomic()`。
3. `select_for_update()` 锁定 `UserProfile`。
4. 买入时检查 `profile.balance >= price * volume`。
5. 买入成功后扣减 `profile.balance`，更新或创建 `Position`，按加权成本更新 `avg_price` 和 `volume`。
6. 卖出时检查 `Position` 存在且 `pos.volume >= volume`。
7. 卖出成功后扣减 `Position.volume`，增加 `profile.balance`。
8. 使用 `get_mock_now()` 设置 `Order.order_time`。
9. 创建 `Order(status='filled')`。
10. 调用 `profile.update_asset_cache()` 刷新资产缓存。

手动下单注意：

- 手动下单当前只创建 `Order`，未创建 `TradeRecord`。
- 手动下单状态直接为 `filled`，没有 pending 撮合阶段。
- 手动下单成交价来自请求 `price`，不是在服务端按当前行情重新撮合。

策略下单入口：

- `TradingEngine.run_all_active_strategies()` 位于 `quant_backend/trade/engine.py`
- `StrategyExecutor.execute()` 位于 `quant_backend/trade/executor.py`
- 自动触发来自 `clock_tick()`。

策略执行窗口：

- 开盘窗口：`09:30 - 09:35`
- 尾盘窗口：`14:50 - 14:59`
- `run_records` 防止同一日期同一窗口重复执行同一策略。

策略撮合流程：

1. `run_all_active_strategies()` 用 `get_mock_now()` 获取当前模拟时间。
2. 只在开盘或尾盘窗口内继续执行。
3. 查询 `Strategy(status='active')`。
4. `execute_strategy(strategy, now, time_type)` 获取用户 `UserProfile` 和当前持仓代码。
5. 读取当前持仓近 30 天日线，构造卖出价格快照。
6. `StrategyExecutor` 解析策略 JSON，读取股票池和因子参数。
7. `StrategyExecutor.execute()` 基于近 30 天 `StockData` 计算动量、偏离、综合分，生成买卖指令。
8. `TradingEngine` 在事务内检查资金或持仓。
9. 买入扣 `profile.balance`，更新 `Position.volume`、`avg_price`。
10. 卖出减 `Position.volume`，必要时清空 `avg_price`，加回 `profile.balance`。
11. 创建 `Order(status='filled', order_time=current_time)`。
12. 创建 `TradeRecord(trade_time=current_time)`。

策略下单注意：

- 策略买入价来自 `StockData.close`，不是分钟线。
- 策略只在特定模拟时间窗口触发，订单不成交时先看模拟时间是否在窗口内。
- 策略撮合失败只写 executor 日志并 `continue`，不会创建失败订单。
- 策略成交后未看到立即调用 `profile.update_asset_cache()`，资产缓存可能依赖后续 `UserInfoView` 或结算刷新。

## 5. 订单、成交、持仓、收益模型关系

关键模型位于 `quant_backend/trade/models.py`。

`Order`：

- 字段：`user`、`strategy`、`stock_code`、`direction`、`price`、`volume`、`status`、`order_time`。
- 表：`trade_order`。
- 手动和策略都会创建 `Order`。

`TradeRecord`：

- 字段：`order`、`stock_code`、`price`、`volume`、`amount`、`fee`、`trade_time`。
- `order` 是 `OneToOneField(Order)`。
- 表：`trade_record`。
- 当前策略撮合会创建，手动下单未创建。

`Position`：

- 字段：`user`、`stock_code`、`volume`、`avg_price`、`frozen_volume`。
- `unique_together = ('user', 'stock_code')`。
- 表：`trade_position`。
- 交易时直接更新，同时 `sync_positions()` 会按已成交订单重建 `volume`。

`DailyPerformance`：

- 字段：`user`、`date`、`total_assets`、`day_profit`、`day_return_rate`、`total_return_rate`。
- `unique_together = ('user', 'date')`。
- 表：`trade_daily_performance`。
- 收盘结算 `record_daily_performance()` 更新。

`IntradayPerformance`：

- 字段：`user`、`time`、`total_assets`、`total_return_rate`。
- 表：`trade_intraday_performance`。
- `record_intraday_snapshot(current_time)` 每 5 分钟边界更新或创建。

`UserProfile`：

- 位于 `quant_backend/users/models.py`。
- 资金字段：`balance`、`withdrawable_cash`、`initial_capital`。
- 缓存字段：`last_market_value`、`last_total_assets`、`daily_profit`、`total_profit`。
- `update_asset_cache()` 用当前模拟时间估值持仓并刷新缓存。

模型关系排查顺序：

1. 先查 `Order(status='filled')` 是否存在，且 `order_time <= get_mock_now()`。
2. 再查 `Position.volume` 是否与订单回放一致。
3. 再查 `UserProfile.balance` 是否被交易扣减或增加。
4. 再调用或观察 `UserProfile.update_asset_cache()` 是否刷新 `last_market_value`、`last_total_assets`、`daily_profit`。
5. 最后查 `DailyPerformance`、`IntradayPerformance` 是否由定时任务按模拟时间写入。

## 6. 资产与收益计算路线

资产刷新入口：

- `UserInfoView.get()`：每次用户信息接口调用 `profile.update_asset_cache()`。
- `PlaceOrderView.post()`：手动下单成功后调用 `profile.update_asset_cache()`。
- `record_daily_performance()`：收盘结算前调用 `profile.update_asset_cache()`。
- `PerformanceView.get(type=intraday)`：末尾调用 `profile.update_asset_cache()` 并缝合最新点。

`UserProfile.update_asset_cache()` 估值逻辑：

1. 读取 `SystemSettings.objects.first().current_mock_time`，无设置则兜底 `timezone.now()`。
2. 查询当前用户 `Position(volume__gt=0)`。
3. 每个持仓优先查 `StockMinuteData(code, date__lte=current_time)` 最新分钟线。
4. 无分钟线时查 `StockData(code, date__lte=current_time.date())` 最新日线。
5. 仍无行情时使用 `pos.avg_price`。
6. `last_market_value = sum(volume * price)`。
7. `last_total_assets = balance + last_market_value`。
8. `total_profit = last_total_assets - initial_capital`。
9. `daily_profit` 使用最近一条 `DailyPerformance(date < current_time.date())` 作昨收基准，否则等于 `total_profit`。

收益曲线入口：

- `PerformanceView.get()` 位于 `quant_backend/trade/views.py`。
- `type=intraday`：按模拟时间、当日订单、当前持仓、分钟行情倒推 5 分钟收益点，并用 `profile.update_asset_cache()` 缝合当前最新点。
- 默认日线：读取 `DailyPerformance` 历史，如果今天没有日收益记录，则用 `calculate_asset_status(request.user, now)` 补一条今天的实时点。

辅助计算：

- `calculate_asset_status(user, target_time)`：按已成交 `Order` 回放现金和持仓，再按目标时间行情估值。
- `trade/utils.py::calculate_holdings_at_time()`：按 `TradeRecord` 回放持仓和成本。
- `trade/utils.py::record_current_assets_snapshot()`：用当前 `Position` 算资产，可写入 `IntradayPerformance` 和 `DailyPerformance`。

疑似风险点：

- 手动下单不创建 `TradeRecord`，因此依赖 `TradeRecord` 的 `calculate_holdings_at_time()` 不会包含手动交易。
- `sync_positions()` 只按 `Order` 回放 `volume`，不会重建 `avg_price`，可能覆盖或丢失持仓均价信息。
- `calculate_asset_status()` 只按订单价格和数量计算现金，不计手续费。
- `record_current_assets_snapshot()` 的收益率字段固定写 `0.0`，若该函数被使用，收益率可能不可信。

## 7. 必须使用 get_mock_now 的逻辑

以下逻辑必须使用模拟时间，不能使用真实时间作为业务时间：

- 行情展示截断：`stocks/views.py` 中市场列表、股票 K 线、指数 K 线必须按模拟时间过滤未来数据。
- 下单时间：`Order.order_time` 必须使用 `get_mock_now()` 或由其传入的 `current_time`。
- 成交时间：`TradeRecord.trade_time` 必须使用模拟时间。
- 策略触发窗口：`TradingEngine.run_all_active_strategies()` 必须使用模拟时间判断 09:30 和 14:50 窗口。
- 持仓同步：`sync_positions()` 必须用模拟时间过滤 `order_time__lte=now`。
- 资产估值：`UserProfile.update_asset_cache()` 必须按模拟时间取分钟线或日线。
- 收益统计：`PerformanceView`、`record_daily_performance()`、`record_intraday_snapshot()` 必须按模拟时间归属日期和时间点。
- 时间接口：`SystemTimeView.get()` 必须返回模拟时间。

已观察到使用模拟时间的位置：

- `trade/time_utils.py::get_mock_now()`
- `trade/views.py::SystemTimeView.get()`
- `trade/views.py::sync_positions()`
- `trade/views.py::PerformanceView.get()`
- `trade/views.py::PlaceOrderView.post()`
- `trade/views.py::PositionListView.get()`
- `trade/engine.py::run_all_active_strategies()`
- `trade/executor.py::StrategyExecutor.__init__()`
- `trade/tasks.py::record_daily_performance()`
- `users/serializers.py::UserFavoriteSerializer._get_market_snapshot()`
- `stocks/views.py` 多个行情接口

## 8. 真实时间误用风险清单

以下是只读梳理发现的疑似风险点，未修复：

- `trade/executor.py::StrategyExecutor.log()` 使用 `timezone.now()` 生成日志时间。若日志被当作业务时间，会与模拟时间不一致。
- `trade/time_utils.py::get_mock_now()` 创建默认设置或异常兜底时使用 `timezone.now()`。数据库缺失或异常时业务会回落真实时间。
- `users/models.py::UserProfile.update_asset_cache()` 在无 `SystemSettings` 时使用 `timezone.now()`。
- `SystemSettings.last_update_time`、`UserProfile.last_update_time`、`Strategy.create_time`、`UserFavorite.add_time` 使用 `auto_now` 或 `auto_now_add`，这是持久化记录的真实创建/更新时间，不应参与模拟交易计算。
- `trade/migrations/0004` 曾给 `Order.order_time`、`TradeRecord.trade_time` 设置 `timezone.now` 默认，`0005` 已移除模型字段默认。仍需确保创建订单时显式传模拟时间。
- `trade/views.py::SystemControlView.get()` 访问已删除字段 `skip_non_trading`。
- `trade/apps.py::start_scheduler()` 和 `trade/management/commands/run_scheduler.py` 引用不存在的任务函数，若调用这些旧入口可能失败。

## 9. 常见问题排查

### 9.1 资产不更新

排查路线：

1. 查是否调用了 `UserInfoView.get()`、`PlaceOrderView.post()` 或 `record_daily_performance()`，这些入口会刷新 `UserProfile` 缓存。
2. 查 `UserProfile.balance` 是否已被下单流程更新。
3. 查 `Position(volume__gt=0)` 是否存在当前持仓。
4. 查 `SystemSettings.current_mock_time` 是否正确，是否晚于目标行情数据时间。
5. 查 `StockMinuteData.date__lte=current_time` 是否有数据；没有则看 `StockData.date__lte=current_time.date()`。
6. 查估值是否退回 `pos.avg_price`，这通常说明行情缺失。
7. 查 `profile.last_total_assets`、`last_market_value`、`daily_profit` 是否是旧缓存。

重点文件：

- `quant_backend/users/views.py::UserInfoView.get`
- `quant_backend/users/models.py::UserProfile.update_asset_cache`
- `quant_backend/trade/views.py::PlaceOrderView.post`
- `quant_backend/trade/tasks.py::record_daily_performance`

### 9.2 订单不成交

手动下单：

1. 查请求参数 `stock_code`、`direction`、`price`、`volume` 是否有效。
2. 买入查 `profile.balance >= price * volume`。
3. 卖出查 `Position` 是否存在，且 `pos.volume >= volume`。
4. 查事务内是否创建 `Order(status='filled')`。
5. 注意手动下单不会创建 `TradeRecord`。

策略下单：

1. 查 `SystemSettings.current_mock_time` 是否在 `09:30-09:35` 或 `14:50-14:59`。
2. 查 `Strategy.status` 是否为 `active`。
3. 查 `strategy.code` 是否为合法 JSON，含 `weight_mom`、`weight_bias`、`top_n` 等参数。
4. 查 `stock_pool` 是否为空，或全部股票模式是否能从 `StockBasicInfo`/`StockData` 读到股票代码。
5. 查近 30 天 `StockData` 是否每只股票至少 6 条收盘价。
6. 买入查 `profile.balance` 是否足够，卖出查 `Position.volume` 是否足够。
7. 查 `run_records` 是否已经记录当天该窗口已执行，避免重复执行。

重点文件：

- `quant_backend/trade/views.py::PlaceOrderView.post`
- `quant_backend/trade/engine.py::TradingEngine.run_all_active_strategies`
- `quant_backend/trade/engine.py::TradingEngine.execute_strategy`
- `quant_backend/trade/executor.py::StrategyExecutor.execute`

### 9.3 持仓不对

排查路线：

1. 先查 `Order(status='filled', order_time__lte=get_mock_now())`。
2. 用订单按时间回放买卖方向和数量，得到理论持仓。
3. 对比 `Position.volume`。
4. 若调用过 `PositionListView` 或 `PositionDetailView`，它们会先执行 `sync_positions()`。
5. 注意 `sync_positions()` 只同步 `volume`，不会同步 `avg_price`。
6. 对手动交易和策略交易混合场景，注意策略会创建 `TradeRecord`，手动不会。

重点文件：

- `quant_backend/trade/views.py::sync_positions`
- `quant_backend/trade/views.py::PositionListView.get`
- `quant_backend/trade/views.py::PositionDetailView.get`
- `quant_backend/trade/models.py::Position`
- `quant_backend/trade/models.py::Order`

### 9.4 收益不对

排查路线：

1. 先确认当前展示的是顶部卡片、日线收益还是分时收益，它们计算路径不同。
2. 顶部卡片来自 `UserInfoView.get()` 返回的 `UserProfile` 缓存字段。
3. 分时收益来自 `PerformanceView.get(type=intraday)` 的倒推计算和最新点缝合。
4. 日线收益来自 `DailyPerformance`，今天无记录时由 `calculate_asset_status()` 临时补点。
5. 查 `DailyPerformance` 中最近一条 `date < current_time.date()` 是否作为日收益基准。
6. 查 `record_daily_performance()` 是否在模拟时间跨过 15:00 时执行过。
7. 查估值行情是否使用了预期的分钟线或日线。
8. 手动交易导致的收益若依赖 `TradeRecord` 回放，可能缺失。

重点文件：

- `quant_backend/users/models.py::UserProfile.update_asset_cache`
- `quant_backend/trade/views.py::PerformanceView.get`
- `quant_backend/trade/views.py::calculate_asset_status`
- `quant_backend/trade/tasks.py::record_daily_performance`
- `quant_backend/debug.py`

### 9.5 时间跳转异常

排查路线：

1. 区分调流速和时间穿越。`set_speed` 不重置交易数据，`set_time` 会调用 `hard_reset_world()`。
2. Admin 的 `TimeFlowSettings` 只改 `time_speed`。
3. Admin 的 `TimeResetSettings` 保存后会调用 `hard_reset_world()`。
4. 查 `SystemSettings.current_mock_time` 是否真的更新。
5. 查 `Order`、`Position`、`DailyPerformance`、`IntradayPerformance` 是否被清空。
6. 查 `UserProfile.balance`、`initial_capital`、`last_total_assets` 是否回到默认资金。
7. 查是否存在多个 `SystemSettings` 记录导致 `first()` 和 `id=1` 不一致。
8. 如果调用 `SystemControlView.get()` 报错，优先检查 `skip_non_trading` 字段访问。

重点文件：

- `quant_backend/trade/views.py::SystemControlView.post`
- `quant_backend/trade/models.py::SystemSettings.hard_reset_world`
- `quant_backend/trade/admin.py::TimeResetSettingsAdmin.save_model`
- `quant_backend/trade/tasks.py::clock_tick`

## 10. 快速定位索引

时间：

- `quant_backend/trade/time_utils.py`
- `quant_backend/trade/models.py::SystemSettings`
- `quant_backend/trade/tasks.py::clock_tick`
- `quant_backend/trade/scheduler.py::start_scheduler`
- `quant_backend/trade/views.py::SystemTimeView`
- `quant_backend/trade/views.py::SystemControlView`

交易：

- `quant_backend/trade/views.py::PlaceOrderView`
- `quant_backend/trade/engine.py::TradingEngine`
- `quant_backend/trade/executor.py::StrategyExecutor`
- `quant_backend/trade/models.py::Order`
- `quant_backend/trade/models.py::TradeRecord`
- `quant_backend/trade/models.py::Position`

资产与收益：

- `quant_backend/users/models.py::UserProfile.update_asset_cache`
- `quant_backend/users/views.py::UserInfoView`
- `quant_backend/trade/views.py::PerformanceView`
- `quant_backend/trade/views.py::calculate_asset_status`
- `quant_backend/trade/tasks.py::record_intraday_snapshot`
- `quant_backend/trade/tasks.py::record_daily_performance`
- `quant_backend/trade/utils.py`

行情时间过滤：

- `quant_backend/stocks/views.py::get_market_index_list_api`
- `quant_backend/stocks/views.py::get_market_index_data_api`
- `quant_backend/stocks/views.py::get_stock_data_api`
- `quant_backend/stocks/views.py::get_market_list_api`
- `quant_backend/users/serializers.py::UserFavoriteSerializer._get_market_snapshot`
