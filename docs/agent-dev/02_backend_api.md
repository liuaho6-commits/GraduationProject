# Django 后端架构与 API 调试文档

本文面向后续 AI agent 调试 Django 后端。重点记录接口入口、输入输出、模型依赖、认证权限、异常定位路径和运行前置条件。

## 1. 后端总览

后端项目目录是 `quant_backend/`，Django project 是 `quant_backend/quant_backend/`。

核心入口文件：

| 类型 | 文件 | 调试用途 |
| --- | --- | --- |
| Django 设置 | `quant_backend/quant_backend/settings.py` | 查数据库、已安装 app、DRF Token 认证、CORS |
| 项目总路由 | `quant_backend/quant_backend/urls.py` | 查所有 app 的 URL 前缀 |
| 启动命令 | `quant_backend/manage.py` | 本地启动、迁移、管理命令入口 |
| 模拟时间工具 | `quant_backend/trade/time_utils.py` | 所有行情、交易、资产接口的“当前时间”来源 |
| 定时任务 | `quant_backend/trade/tasks.py`、`quant_backend/trade/scheduler.py` | 模拟时钟推进、策略执行、资产快照、收盘结算 |

已安装 app：

| App | 主要职责 |
| --- | --- |
| `stocks` | 股票/指数基础信息、日线、5 分钟线、行情列表、K 线接口 |
| `users` | 注册、登录、Token、用户资产信息、自选股 |
| `trade` | 策略、订单、持仓、资产收益、模拟时间控制、调度器 |
| `managers` | 管理员登录、后台统计、用户列表，但当前未挂载到总路由 |
| `backtest` | Spark 多因子回测任务和回测结果 |

数据库配置在 `settings.py`：MySQL，库名 `quant_db`，用户 `root`，密码 `liuhao`，host `127.0.0.1`，port `3306`。

DRF 默认认证在 `settings.py`：`TokenAuthentication`。只有 view 显式设置 `permission_classes = [IsAuthenticated]` 或自定义权限时才要求 Token；函数式 `@api_view` 和 `AllowAny` 接口默认开放。

## 2. URL 路由入口

总路由文件：`quant_backend/quant_backend/urls.py`。

| 前缀 | Include | 说明 |
| --- | --- | --- |
| `/admin/` | Django admin | Django 管理后台 |
| `/trade/api/` | `trade.urls` | 交易接口方案 A |
| `/api/trade/` | `trade.urls` | 交易接口方案 B，兼容前端另一种前缀 |
| `/users/api/` | `users.urls` | 用户接口方案 A |
| `/api/users/` | `users.urls` | 用户接口方案 B |
| `/stocks/` | `stocks.urls` | 股票行情接口，注意 app 内部 URL 仍带 `/api/` |
| `/api/backtest/` | `backtest.urls` | 回测接口 |

已知路由问题：

| 问题 | 影响 | 定位文件 |
| --- | --- | --- |
| `managers.urls` 未被 include | `/managers/...` 或 `/api/managers/...` 当前不可达，除非另行挂载 | `quant_backend/quant_backend/urls.py`、`managers/urls.py` |
| `trade/urls.py` 里 `time/` 重复注册两次 | 行为通常无害，但调试路由表时会看到重复 | `trade/urls.py` |
| `quant_backend/urls.py` 重复导入 `path, include` | 无运行影响，只是冗余 | `quant_backend/quant_backend/urls.py` |

## 3. 认证与权限

通用请求头：

```http
Authorization: Token <token>
```

Token 来源：用户登录或管理员登录成功后返回。

权限分布：

| 接口类型 | 权限 | 文件 |
| --- | --- | --- |
| 用户登录、注册 | `AllowAny` | `users/views.py` |
| 用户信息、自选股 | `IsAuthenticated` | `users/views.py` |
| 交易、持仓、策略、资产、系统时间控制 | `IsAuthenticated` | `trade/views.py` |
| 股票行情和 K 线 | 默认开放 | `stocks/views.py` |
| 回测运行 | `AllowAny` | `backtest/views.py` |
| 管理员 dashboard、用户列表 | `IsSuperUser` | `managers/views.py`、`managers/permissions.py` |

`IsSuperUser` 逻辑：`request.user.is_authenticated` 且 `request.user.is_superuser` 为真。

## 4. stocks App

### 4.1 职责与核心文件

| 文件 | 调试用途 |
| --- | --- |
| `stocks/urls.py` | 股票/指数 API 路由 |
| `stocks/views.py` | 行情列表、股票 K 线、指数概览、指数 K 线 |
| `stocks/models.py` | 股票和指数基础表、日线表、分钟线表 |
| `stocks/serializers.py` | K 线数据序列化，基本是 `fields = '__all__'` |
| `stocks/management/commands/*.py` | 股票/指数数据下载、模拟数据填充 |

### 4.2 模型

| 模型 | 表名 | 核心字段 | 依赖接口 |
| --- | --- | --- | --- |
| `StockBasicInfo` | 默认 `stocks_stockbasicinfo` | `code`, `name` | 行情列表、自选股、订单/持仓显示名称 |
| `StockData` | `stock_data_daily` | `code`, `date`, `open`, `high`, `low`, `close`, `volume`, `amount` | 股票日线、涨跌幅、资产估值、回测 |
| `StockMinuteData` | `stock_data_minute` | `code`, `date`, OHLCV, `amount` | 股票分钟线、实时价格、收益分时、交易资产估值 |
| `MarketIndexBasicInfo` | `market_index_basic` | `code`, `name`, `market` | 指数概览、指数详情 |
| `MarketIndexDailyData` | `market_index_daily` | `code`, `date`, OHLCV, `change_pct`, `change_amount` | 指数日线、指数概览 |
| `MarketIndexMinuteData` | `market_index_minute` | `code`, `date`, OHLCV, `source` | 指数 5 分钟线 |

### 4.3 接口

#### GET `/stocks/api/indices/`

View：`get_market_index_list_api`。

用途：返回大盘指数概览卡片，按 `INDEX_ORDER` 优先排序。

参数：无。

依赖模型：`MarketIndexBasicInfo`、`MarketIndexDailyData`。

时间依赖：`trade.time_utils.get_mock_now()`，按模拟日期过滤 `date <= mock_date`。

返回结构：

```json
{
  "code": 200,
  "current_mock_time": "YYYY-MM-DD HH:mm:ss",
  "data": [
    {
      "code": "sh.000001",
      "name": "上证指数",
      "market": "sh",
      "price": 0,
      "change": 0,
      "change_amount": 0,
      "date": "YYYY-MM-DD",
      "volume": 0,
      "amount": 0
    }
  ]
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 返回空数组或 price 为 0 | `market_index_basic`、`market_index_daily` 是否有对应 code 和模拟日期之前的数据 |
| 时间不对 | `trade/time_utils.py`、`trade.models.SystemSettings.current_mock_time` |
| 指数顺序异常 | `stocks/views.py` 的 `INDEX_ORDER` |

#### GET `/stocks/api/index/<index_code>/`

View：`get_market_index_data_api`。

用途：返回指数日线或 5 分钟 K 线。

路径参数：`index_code`，例如 `sh.000001`、`sz.399001`。

Query 参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `freq` | `daily` | `daily` 返回日线；`min` 或 `5min` 返回 5 分钟线 |
| `limit` | daily 默认 `1200`，分钟默认 `500` | 最大 `5000` |

依赖模型：`MarketIndexBasicInfo`、`MarketIndexDailyData`、`MarketIndexMinuteData`。

返回结构：

```json
{
  "code": 200,
  "name": "上证指数",
  "index_code": "sh.000001",
  "freq": "daily",
  "latest_price": 0,
  "latest_time": "YYYY-MM-DD",
  "current_mock_time": "YYYY-MM-DD HH:mm:ss",
  "data": [
    {
      "id": 1,
      "code": "sh.000001",
      "date": "YYYY-MM-DD",
      "open": 0,
      "high": 0,
      "low": 0,
      "close": 0,
      "volume": 0,
      "amount": 0
    }
  ]
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| `data` 为空 | 对应指数日线/分钟线表是否有 `code=index_code` 且时间不晚于模拟时间 |
| `name` 为 `未知指数` | `MarketIndexBasicInfo` 缺对应 code |
| 分钟线缺失 | `download_market_index_data.py` 的 pytdx 下载、`MarketIndexMinuteData` 表 |

#### GET `/stocks/api/data/<stock_code>/`

View：`get_stock_data_api`。

用途：返回股票详情页 K 线。

路径参数：`stock_code`，例如 `sh.688256`。

Query 参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `freq` | `daily` | `daily` 返回日线；`min` 返回 5 分钟线 |
| `date` | 无 | 仅 `freq=min` 时用于历史回看某天，格式 `YYYY-MM-DD` |

依赖模型：`StockBasicInfo`、`StockData`、`StockMinuteData`。

时间依赖：`get_mock_now()`。

返回结构：

```json
{
  "code": 200,
  "name": "股票名",
  "stock_code": "sh.688256",
  "freq": "daily",
  "target_date": null,
  "pre_close": 0,
  "current_mock_time": "YYYY-MM-DD HH:mm:ss",
  "data": [
    {
      "id": 1,
      "code": "sh.688256",
      "date": "YYYY-MM-DD 或 ISO datetime",
      "open": 0,
      "high": 0,
      "low": 0,
      "close": 0,
      "volume": 0,
      "amount": 0
    }
  ]
}
```

调试要点：

| 现象 | 先看哪里 |
| --- | --- |
| 分钟线只显示旧数据 | `StockMinuteData.date <= get_mock_now()` 的过滤逻辑；`SystemSettings.current_mock_time` |
| `pre_close` 为 0 | `StockData` 缺第一根分钟线之前的日线记录 |
| `name` 为 `未知股票` | `StockBasicInfo` 缺对应 code |
| 控制台出现 `[API] Stock...` | 这是 view 中直接 `print`，定位 `stocks/views.py` |

#### GET `/stocks/api/market/`

View：`get_market_list_api`。

用途：分页返回行情列表，包含当前价和 1 周、1 年、2 年、3 年涨跌幅。

Query 参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `page` | DRF 默认 | 页码 |
| `page_size` | `20` | 最大 `100` |
| `sort_prop` | `code` | 支持数据库排序字段 `code`、`name`；也可对返回计算字段内存排序 |
| `sort_order` | `ascending` | `ascending` 或 `descending` |

依赖模型：`StockBasicInfo`、`StockData`、`StockMinuteData`。

返回结构是 DRF 分页响应：

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": [
    {
      "code": "sh.688256",
      "name": "寒武纪",
      "price": 0,
      "date": "YYYY-MM-DD HH:mm",
      "change": 0,
      "change_1w": 0,
      "change_1y": 0,
      "change_2y": 0,
      "change_3y": 0
    }
  ]
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 行情列表为空 | `StockBasicInfo.objects.all()` 是否有数据 |
| 当前价不是预期 | `StockMinuteData` 是否有模拟时间之前最近数据；没有则回退 `StockData` |
| 涨跌幅全为 0 | 历史日线不足，检查 `StockData` 中对应日期前的数据 |
| 分页结构不含 `code: 200` | 这是 DRF `PageNumberPagination.get_paginated_response` 的原生结构，不是业务包装 |

### 4.4 数据导入和前置条件

股票数据导入入口：

| 命令/脚本 | 用途 | 依赖 |
| --- | --- | --- |
| `python manage.py fill_mock_data` | 清空并下载/补全少量目标股票数据 | `akshare`, `pandas`, `numpy`, `tqdm` |
| `python manage.py init_minute_data` | 下载指定股票 3 年日线和分钟线 | `akshare`, `pandas`, `tqdm` |
| `python manage.py download_real_3y` | 用 baostock 下载分钟线 | `baostock`, `pandas`, `tqdm` |
| `python manage.py download_market_index_data` | 下载指数日线和 5 分钟线 | `akshare`, `pytdx`, `pandas`, `tqdm` |
| `python download_hs300_to_db.py` | 沪深 300 数据下载到本地 CSV 再入库 | `baostock`, `pandas`, `tqdm` |

注意：多个数据命令会清空表或按范围先删后插。调试接口时不要随意运行这些命令，除非明确需要重建数据。

## 5. users App

### 5.1 职责与核心文件

| 文件 | 调试用途 |
| --- | --- |
| `users/urls.py` | 用户 API 路由 |
| `users/views.py` | 登录、注册、用户资产、自选股 |
| `users/models.py` | `UserProfile` 和 `UserFavorite` |
| `users/serializers.py` | 注册校验、自选股行情快照 |

完整 URL 有两套前缀：`/users/api/...` 和 `/api/users/...`。

### 5.2 模型

| 模型 | 表名 | 核心字段 | 依赖接口 |
| --- | --- | --- | --- |
| Django `User` | `auth_user` | `username`, `password`, `is_active`, `is_superuser` | 登录、注册、权限 |
| `UserProfile` | `user_profile` | `balance`, `withdrawable_cash`, `initial_capital`, `last_market_value`, `last_total_assets`, `daily_profit`, `total_profit` | 用户信息、交易、收益、结算 |
| `UserFavorite` | `user_favorite` | `user`, `stock`, `add_time` | 自选股列表 |

`UserProfile.update_asset_cache()` 是资产计算核心之一，会读取 `trade.Position`、`trade.SystemSettings`、`stocks.StockMinuteData`、`stocks.StockData`、`trade.DailyPerformance`。

### 5.3 接口

#### POST `/users/api/login/` 或 `/api/users/login/`

View：`LoginView.post`。

权限：`AllowAny`。

Body：

```json
{
  "username": "user",
  "password": "password"
}
```

返回成功：

```json
{
  "code": 200,
  "msg": "登录成功",
  "data": {
    "token": "...",
    "username": "user"
  }
}
```

失败情况：缺用户名/密码返回 `code: 400`；认证失败返回 `code: 400`；用户禁用返回 `code: 403`。

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| Token 不返回 | `rest_framework.authtoken` 是否迁移；`authtoken_token` 表 |
| 密码正确但失败 | Django `authenticate`、`auth_user.is_active`、密码哈希 |

#### POST `/users/api/register/` 或 `/api/users/register/`

View：`RegisterView.post`。

权限：`AllowAny`。

Body：

```json
{
  "username": "user",
  "password": "123456",
  "password_confirm": "123456",
  "phone": "13800000000"
}
```

返回成功：`{"code": 200, "msg": "注册成功"}`。

依赖：`RegisterSerializer` 创建 Django `User` 和 `UserProfile`，默认 `balance=200000.00`、`initial_capital=200000.00`。

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 注册失败只返回第一条错误 | `users/serializers.py` 的 `RegisterSerializer.validate` 和 `users/views.py` 错误拼接 |
| 用户有了但没 profile | `RegisterSerializer.create`；也可检查历史用户是否绕过注册创建 |

#### GET `/users/api/info/` 或 `/api/users/info/`

View：`UserInfoView.get`。

权限：`IsAuthenticated`。

依赖模型：`UserProfile`、`Position`、`SystemSettings`、`StockMinuteData`、`StockData`、`DailyPerformance`。

行为：每次请求会 `get_or_create` profile，然后调用 `profile.update_asset_cache()` 实时刷新资产缓存。

返回结构：

```json
{
  "code": 200,
  "data": {
    "total_assets": 200000.0,
    "market_value": 0.0,
    "balance": 200000.0,
    "withdrawable": 200000.0,
    "daily_profit": 0.0,
    "total_profit": 0.0,
    "initial_capital": 200000.0,
    "username": "user"
  }
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 401 未认证 | 请求头是否是 `Authorization: Token <token>` |
| 资产不更新 | `UserProfile.update_asset_cache()`、`SystemSettings.current_mock_time`、`Position`、股票分钟/日线价格 |
| 总资产异常 | 交易接口是否正确更新 `balance` 和 `Position`；收盘记录 `DailyPerformance` |

#### GET `/users/api/favorites/` 或 `/api/users/favorites/`

View：`UserFavoriteView.get`。

权限：`IsAuthenticated`。

依赖模型：`UserFavorite`、`StockBasicInfo`、`StockData`、`StockMinuteData`。

返回结构：

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "stock": "sh.688256",
      "name": "寒武纪",
      "add_time": "ISO datetime",
      "price": 0,
      "change": 0
    }
  ]
}
```

行情快照逻辑在 `UserFavoriteSerializer._get_market_snapshot()`，基本复刻 `stocks.views.get_market_list_api` 的当前价与昨收逻辑。

#### POST `/users/api/favorites/` 或 `/api/users/favorites/`

View：`UserFavoriteView.post`。

权限：`IsAuthenticated`。

Body：

```json
{
  "code": "sh.688256"
}
```

返回：成功 `code: 200`；股票不存在 `code: 404`；重复添加 `code: 400`。

#### DELETE `/users/api/favorites/` 或 `/api/users/favorites/`

View：`UserFavoriteView.delete`。

权限：`IsAuthenticated`。

参数：body 或 query string 中传 `code`。

示例：`DELETE /api/users/favorites/?code=sh.688256`。

返回：成功 `code: 200`；未找到 `code: 400`。

## 6. trade App

### 6.1 职责与核心文件

| 文件 | 调试用途 |
| --- | --- |
| `trade/urls.py` | 交易 API 路由 |
| `trade/views.py` | 交易、持仓、策略、收益、系统时间控制接口 |
| `trade/models.py` | 策略、订单、持仓、成交、收益、系统时间 |
| `trade/serializers.py` | 策略、订单、持仓序列化 |
| `trade/time_utils.py` | 模拟时间读写 |
| `trade/tasks.py` | 时钟心跳、日内快照、收盘结算 |
| `trade/scheduler.py` | 自动启动的 APScheduler 配置 |
| `trade/engine.py` | 激活策略执行与订单撮合 |
| `trade/executor.py` | 多因子策略解析、打分、生成买卖信号 |

完整 URL 有两套前缀：`/trade/api/...` 和 `/api/trade/...`。

所有 APIView 都使用 `permission_classes = [IsAuthenticated]`。

### 6.2 模型

| 模型 | 表名 | 核心字段 | 调试用途 |
| --- | --- | --- | --- |
| `Strategy` | `trade_strategy` | `user`, `name`, `code`, `stock_pool`, `status`, `total_return` | 策略 CRUD 和自动执行 |
| `Position` | `trade_position` | `user`, `stock_code`, `volume`, `avg_price`, `frozen_volume` | 持仓、资产估值、卖出校验 |
| `Order` | `trade_order` | `user`, `strategy`, `stock_code`, `direction`, `price`, `volume`, `status`, `order_time` | 订单列表、持仓同步、收益计算 |
| `TradeRecord` | `trade_record` | `order`, `stock_code`, `price`, `volume`, `amount`, `fee`, `trade_time` | 自动策略撮合记录，手工下单未写入该表 |
| `DailyPerformance` | `trade_daily_performance` | `user`, `date`, `total_assets`, `day_profit`, `day_return_rate`, `total_return_rate` | 日收益曲线、昨日资产基准 |
| `IntradayPerformance` | `trade_intraday_performance` | `user`, `time`, `total_assets`, `total_return_rate` | 定时快照，目前接口主要实时计算 |
| `SystemSettings` | `system_settings` | `current_mock_time`, `time_speed`, `last_update_time` | 模拟时间、时钟流速 |

代理模型：`TimeFlowSettings`、`TimeResetSettings` 继承 `SystemSettings`，用于 Django admin 展示不同控制入口，不建新表。

### 6.3 接口

#### GET `/api/trade/time/` 或 `/trade/api/time/`

View：`SystemTimeView.get`。

用途：读取模拟系统时间。

返回结构：

```json
{
  "code": 200,
  "data": {
    "system_time": "YYYY-MM-DD HH:mm:ss",
    "timestamp": 1710000000.0
  }
}
```

依赖：`get_mock_now()` -> `SystemSettings.current_mock_time`。

异常定位：`trade/time_utils.py`、`trade.models.SystemSettings`。

#### GET `/api/trade/performance/?type=daily|intraday`

View：`PerformanceView.get`。

用途：返回收益曲线。

Query 参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `type` | `daily` | `daily` 返回日收益；`intraday` 返回日内 5 分钟收益 |

依赖模型：`UserProfile`、`DailyPerformance`、`Order`、`Position`、`StockData`、`StockMinuteData`。

`daily` 返回结构：

```json
{
  "code": 200,
  "data": [
    {
      "date": "YYYY-MM-DD",
      "total_return_rate": 0,
      "profit": 0,
      "day_profit": 0,
      "total_assets": 200000
    }
  ]
}
```

`intraday` 返回结构：

```json
{
  "code": 200,
  "data": [
    {
      "time": "09:30",
      "total_return_rate": 0,
      "profit": 0
    }
  ]
}
```

调试路径：

| 现象 | 先看哪里 |
| --- | --- |
| `intraday` 返回空数组 | 当前模拟日期是否有 `StockMinuteData`；09:30 前也会返回空 |
| `daily` 今日重复或缺失 | `DailyPerformance` 是否有今日记录；view 会在没有今日记录时临时计算追加 |
| 收益和顶部资产不一致 | `UserProfile.update_asset_cache()`、`PerformanceView` 中基准资产和当前资产计算 |
| 资产线断点 | `Order.order_time`、`Position.volume`、`StockMinuteData` 是否覆盖当前时间区间 |

#### POST `/api/trade/transfer/` 或 `/trade/api/transfer/`

View：`FundTransferView.post`。

用途：资金划转，正数增加资金，负数取出资金。

Body：

```json
{
  "amount": 10000
}
```

依赖模型：`UserProfile`。

行为：事务锁定当前用户 profile；`balance += amount`；`initial_capital += amount`。负数时余额不足返回 `code: 400`。

返回成功：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "balance": 210000.0
  }
}
```

异常定位：`users.models.UserProfile` 是否存在；Decimal 转换是否失败。

#### GET `/api/trade/strategy/` 或 `/trade/api/strategy/`

View：`StrategyView.get`。

用途：获取当前用户策略列表。

返回：`{"code": 200, "data": [...]}`，`data` 来自 `StrategySerializer(fields='__all__')`。

依赖模型：`Strategy`。

#### POST `/api/trade/strategy/` 或 `/trade/api/strategy/`

View：`StrategyView.post`。

用途：创建策略或更新策略。

创建 Body：

```json
{
  "name": "多因子策略",
  "code": "{\"weight_mom\": 0.5, \"weight_bias\": 0.5, \"top_n\": 2}",
  "stock_pool": "sh.688256,sz.300308"
}
```

更新 Body：

```json
{
  "id": 1,
  "status": "active",
  "name": "多因子策略",
  "code": "{\"weight_mom\": 0.5, \"weight_bias\": 0.5, \"top_n\": 2}",
  "stock_pool": "__ALL__"
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 有值则更新，无值则创建 |
| `status` | `active`、`paused`、`stopped` |
| `code` | 在自动策略执行器中按 JSON 解析 |
| `stock_pool` | 英文逗号分隔；`__ALL__`、`ALL`、`ALL_STOCKS`、`全部`、`全部股票` 表示全市场 |

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 策略保存成功但不执行 | `status` 是否为 `active`；模拟时间是否在 09:30-09:35 或 14:50-14:59 |
| 自动执行提示参数解析失败 | `trade/executor.py` 的 `json.loads(strategy.code)` |
| 全市场过慢 | `StrategyExecutor.get_pool()`、`StockBasicInfo` 数量、`StockData` 最近 30 天数据 |

#### DELETE `/api/trade/strategy/` 或 `/trade/api/strategy/`

View：`StrategyView.delete`。

参数：body 或 query string 中传 `id`。

返回：成功 `code: 200`；缺 ID `code: 400`；不存在 `code: 404`。

#### GET `/api/trade/orders/` 或 `/trade/api/orders/`

View：`OrderListView.get`。

用途：返回当前用户最近 50 条订单，按 `order_time` 倒序。

依赖模型：`Order`、`StockBasicInfo`。

返回：`{"code": 200, "data": [...]}`，订单字段来自 `OrderSerializer(fields='__all__')`，额外包含 `stock_name`。

调试路径：订单不显示先查 `trade_order.user_id` 是否为当前 Token 用户。

#### POST `/api/trade/place_order/` 或 `/trade/api/place_order/`

View：`PlaceOrderView.post`。

用途：手工下单，立即按传入价格成交。

Body：

```json
{
  "stock_code": "sh.688256",
  "direction": "buy",
  "price": 100.0,
  "volume": 100
}
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `stock_code` | 是 | 会执行 `.strip()`，为空或缺失会抛异常并返回 `code: 500` |
| `direction` | 是 | `buy` 或 `sell` |
| `price` | 是 | Decimal 转换 |
| `volume` | 是 | int 转换，未强制 100 股整数倍 |

依赖模型：`UserProfile`、`Position`、`Order`。

行为：

| 方向 | 行为 |
| --- | --- |
| `buy` | 检查余额，扣 `balance`，更新/创建 `Position` 和均价，创建 `Order` |
| `sell` | 检查持仓，扣 `Position.volume`，加 `balance`，创建 `Order` |

返回成功：`{"code": 200, "msg": "交易成功"}`。

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 余额不足 | `UserProfile.balance` |
| 持仓不足 | `Position.volume`；请求用户是否正确 |
| 下单后资产没变 | `profile.update_asset_cache()`、股票价格表、`Position` |
| 持仓与订单不一致 | `sync_positions(user)` 会按已成交订单重新校准持仓，但均价不参与重算 |

注意：手工下单只创建 `Order`，不会创建 `TradeRecord`。

#### GET `/api/trade/positions/` 或 `/trade/api/positions/`

View：`PositionListView.get`。

用途：返回当前用户持仓列表和实时盈亏。

依赖模型：`Position`、`Order`、`StockData`、`StockMinuteData`、`StockBasicInfo`。

返回结构：

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "stock_name": "寒武纪",
      "user": 1,
      "stock_code": "sh.688256",
      "volume": 100,
      "avg_price": 100.0,
      "frozen_volume": 0,
      "current_price": 101.0,
      "market_value": 10100.0,
      "profit": 100.0,
      "profit_rate": 1.0
    }
  ]
}
```

价格逻辑：15:00 后优先当日日线；否则用当日模拟时间之前最近分钟线；再回退上一交易日线；最后回退持仓均价。

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 持仓为空 | `Position.volume > 0`；`sync_positions()` 是否按订单把持仓清零 |
| 盈亏为 0 | `avg_price`、分钟/日线当前价格 |
| `stock_name` 显示代码 | `StockBasicInfo` 缺基础信息 |

#### GET `/api/trade/position/<stock_code>/` 或 `/trade/api/position/<stock_code>/`

View：`PositionDetailView.get`。

用途：返回某只股票当前持仓股数。

返回：

```json
{
  "code": 200,
  "data": {
    "stock_code": "sh.688256",
    "volume": 100
  }
}
```

依赖模型：`Position`、`Order`。

异常定位：如果返回 0，查当前 Token 用户、`Position`、`Order.status='filled'`。

#### GET `/api/trade/control/` 或 `/trade/api/control/`

View：`SystemControlView.get`。

用途：读取模拟时间控制设置。

依赖模型：`SystemSettings`。

预期返回：

```json
{
  "code": 200,
  "data": {
    "current_time": "ISO datetime",
    "time_speed": 1.0,
    "skip_non_trading": false
  }
}
```

已知问题：`SystemSettings.skip_non_trading` 字段已在迁移 `trade/migrations/0005_timeflowsettings_timeresetsettings_and_more.py` 中删除，但 `SystemControlView.get` 仍读取该属性，可能触发 `AttributeError` 并导致 500。

定位文件：`trade/views.py`、`trade/models.py`、`trade/migrations/0005_timeflowsettings_timeresetsettings_and_more.py`。

#### POST `/api/trade/control/` 或 `/trade/api/control/`

View：`SystemControlView.post`。

用途：调整模拟时间流速或直接跳转模拟时间。

Body 示例，设置流速：

```json
{
  "action": "set_speed",
  "speed": 2.0
}
```

Body 示例，设置时间：

```json
{
  "action": "set_time",
  "target_time": "2025-01-02 09:30:00"
}
```

行为：

| action | 行为 |
| --- | --- |
| `set_speed` | 更新 `SystemSettings.time_speed` |
| `set_time` | 解析 `target_time`，更新 `current_mock_time`，然后调用 `settings.hard_reset_world()` |

重要副作用：`set_time` 会清空 `Order`、`Position`、`DailyPerformance`、`IntradayPerformance`，并重置所有 `UserProfile` 资金为 200000。

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 时间跳转后订单消失 | 这是 `SystemSettings.hard_reset_world()` 的设计行为 |
| `target_time` 报错 | Python `datetime.fromisoformat` 支持的格式；日期字符串会自动补 `09:30:00` |
| 流速不生效 | `trade/scheduler.py` 是否启动；`trade/tasks.clock_tick()` 是否每秒更新 |

### 6.4 定时任务和策略执行

自动启动路径：`trade/apps.py` 的 `TradeConfig.ready()` 在 `RUN_MAIN == 'true'` 时调用 `trade.scheduler.start_scheduler()`。

当前实际调度器：`trade/scheduler.py` 每秒执行 `clock_tick()`。

`clock_tick()` 行为：

| 步骤 | 文件 | 说明 |
| --- | --- | --- |
| 读取设置 | `trade/tasks.py` | `SystemSettings.objects.first()` |
| 推进模拟时间 | `trade/tasks.py` | `current_mock_time += seconds(time_speed)` |
| 5 分钟快照 | `trade/tasks.py` | 分钟变化且新分钟能被 5 整除时调用 `record_intraday_snapshot()` |
| 收盘结算 | `trade/tasks.py` | 从 15:00 前跨到 15:00 后时调用 `record_daily_performance()` |
| 执行策略 | `trade/engine.py` | `TradingEngine.run_all_active_strategies()` |

策略执行触发窗口：09:30-09:35 或 14:50-14:59。策略 `status` 必须为 `active`。

已知调试问题：

| 问题 | 影响 | 定位文件 |
| --- | --- | --- |
| `trade/management/commands/run_scheduler.py` 导入 `run_active_strategies`、`record_intraday_assets`，但 `trade/tasks.py` 中不存在这些函数 | 执行 `python manage.py run_scheduler` 会 ImportError | `trade/management/commands/run_scheduler.py`、`trade/tasks.py` |
| `trade/apps.py` 中备用 `start_scheduler` 方法也引用不存在函数 | 如果调用该方法会失败；当前 `ready()` 调用的是 `trade.scheduler.start_scheduler()` | `trade/apps.py` |
| 生产或非 `runserver` 环境可能不满足 `RUN_MAIN == 'true'` | 调度器可能不自动启动 | `trade/apps.py` |

## 7. managers App

### 7.1 职责与核心文件

| 文件 | 调试用途 |
| --- | --- |
| `managers/urls.py` | 管理接口路由，但当前未挂载总路由 |
| `managers/views.py` | 管理员登录、后台统计、用户列表 |
| `managers/permissions.py` | `IsSuperUser` 权限 |
| `managers/models.py` | 当前无业务模型 |

当前总路由未 include `managers.urls`，所以以下路径只是 app 内定义，不是实际可访问完整 URL。要调试 404，优先看 `quant_backend/quant_backend/urls.py`。

### 7.2 接口

#### POST `managers/login/`，当前未挂载

View：`AdminLoginView.post`。

权限：未显式设置，实际逻辑自行校验 `user.is_superuser`。

Body：

```json
{
  "username": "admin",
  "password": "password"
}
```

返回成功：

```json
{
  "code": 200,
  "msg": "管理员登录成功",
  "token": "...",
  "username": "admin",
  "role": "admin"
}
```

失败：非管理员 `403`；账号密码错误 `401`。

#### GET `managers/dashboard/`，当前未挂载

View：`DashboardStatsView.get`。

权限：`IsSuperUser`。

依赖模型：Django `User`、`StockBasicInfo`、`StockData`、`UserProfile`。

返回结构：

```json
{
  "code": 200,
  "data": {
    "total_users": 0,
    "total_stocks": 0,
    "total_records": 0,
    "market_capital": 0
  }
}
```

#### GET `managers/users/`，当前未挂载

View：`UserListView.get`。

权限：`IsSuperUser`。

依赖模型：Django `User`、`UserProfile`。

返回结构：

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "username": "user",
      "email": "",
      "phone": "13800000000",
      "balance": 200000,
      "date_joined": "YYYY-MM-DD HH:mm"
    }
  ]
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| 管理接口 404 | `managers.urls` 未在 `quant_backend/urls.py` 挂载 |
| 403 | 当前 Token 用户不是 `is_superuser` |
| 管理员登录有 token 但 dashboard 403 | 用管理员登录返回的 token 请求；确认 `auth_user.is_superuser=1` |

## 8. backtest App

### 8.1 职责与核心文件

| 文件 | 调试用途 |
| --- | --- |
| `backtest/urls.py` | 回测 API 路由 |
| `backtest/views.py` | 创建回测任务、调用 Spark 引擎、保存结果 |
| `backtest/models.py` | 因子、任务、结果 |
| `backtest/engine.py` | PySpark 多因子计算和组合模拟 |

实际完整 URL：`/api/backtest/run/`。

权限：`AllowAny`，不要求 Token。

### 8.2 模型

| 模型 | 表名 | 核心字段 | 调试用途 |
| --- | --- | --- | --- |
| `Factor` | `backtest_factor` | `name`, `code`, `description`, `is_active` | 因子元数据，目前 run 接口未直接使用 |
| `BacktestTask` | `backtest_task` | `user`, `task_name`, `start_date`, `end_date`, `initial_capital`, `status`, `factor_weights`, `error_message` | 回测任务状态和错误记录 |
| `BacktestResult` | `backtest_result` | `task`, `annualized_return`, `equity_curve`, `positions_history` | 回测结果落库 |

### 8.3 接口

#### POST `/api/backtest/run/`

View：`RunBacktestView.post`。

用途：运行多因子回测并返回资金曲线和每日持仓。

Body：

```json
{
  "task_name": "多因子回测_测试",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 100000,
  "weight_mom": 0.5,
  "weight_bias": 0.5,
  "top_n": 2
}
```

默认值：

| 参数 | 默认 |
| --- | --- |
| `task_name` | `多因子回测_MMDD_HHMM` |
| `start_date` | `2025-01-01` |
| `end_date` | `2025-12-31` |
| `initial_capital` | `100000.0` |
| `weight_mom` | `0.5` |
| `weight_bias` | `0.5` |
| `top_n` | `2` |

依赖模型：Django `User`、`BacktestTask`、`BacktestResult`、`StockData`、`StockBasicInfo`。

执行流程：

| 步骤 | 文件 | 说明 |
| --- | --- | --- |
| 选择用户 | `backtest/views.py` | 使用 `User.objects.first()`，不是当前请求用户 |
| 创建任务 | `backtest/views.py` | `status='running'` |
| 初始化 Spark | `backtest/engine.py` | local 模式，设置 `PYSPARK_PYTHON`、`SPARK_LOCAL_IP` |
| 读取数据 | `SparkBacktestEngine.load_data()` | 从 `StockData` 读取日期范围内 `date`, `code`, `close` |
| 因子计算 | `compute_multi_factors()` | momentum、bias、截面 z-score、total_score |
| 模拟组合 | `simulate_strategy()` | 每日选 top_n，下一日收益累乘 |
| 写结果 | `backtest/views.py` | 写 `BacktestResult`，任务改 `completed` |

返回成功：

```json
{
  "code": 200,
  "data": {
    "task_id": 1,
    "total_return": 0.1,
    "annualized_return": 0.2,
    "final_capital": 110000.0,
    "equity_curve": [
      {
        "date": "YYYY-MM-DD",
        "equity": 100000.0,
        "daily_return": 0.01
      }
    ],
    "trade_records": [
      {
        "date": "YYYY-MM-DD",
        "stocks": "寒武纪(100.0), 中际旭创(90.0)",
        "daily_return": 0.01,
        "equity": 100000.0
      }
    ]
  }
}
```

失败返回：

```json
{
  "code": 500,
  "message": "引擎回测失败: ..."
}
```

异常定位：

| 现象 | 先看哪里 |
| --- | --- |
| `系统无用户，请先创建管理员` | `auth_user` 为空，view 使用 `User.objects.first()` |
| 指定区间无数据 | `StockData` 是否有 `start_date <= date <= end_date` 数据 |
| Spark 初始化失败 | `pyspark`、Java 环境、Windows 本机 Spark 配置、`backtest/engine.py` |
| `portfolio_df.empty` | 因子计算后没有有效数据，通常是每个股票少于 5 天日线或 `next_return` 为空 |
| 任务失败但数据库有 running/failed 记录 | 查 `backtest_task.error_message` |

## 9. 常见调试路径

### 9.1 先确认请求有没有打到正确路由

1. 看完整 URL 是否匹配 `quant_backend/quant_backend/urls.py` 的前缀。
2. `trade` 和 `users` 有双前缀，分别尝试 `/api/trade/...` 与 `/trade/api/...`、`/api/users/...` 与 `/users/api/...`。
3. `stocks` 的完整路径是 `/stocks/api/...`，不是 `/api/stocks/...`。
4. `managers` 当前没有总路由挂载，404 是预期。

### 9.2 401 或 403

1. 401：检查请求头 `Authorization: Token <token>`。
2. 401：检查 `rest_framework.authtoken` 迁移和 `authtoken_token` 表。
3. 403：普通用户访问管理员接口，检查 `auth_user.is_superuser`。
4. 用户禁用：`LoginView` 会返回 `code: 403` 和 `账户已被禁用`。

### 9.3 行情、K 线、价格异常

1. 股票基础信息：`StockBasicInfo`。
2. 股票日线：`StockData`，表名 `stock_data_daily`。
3. 股票分钟线：`StockMinuteData`，表名 `stock_data_minute`。
4. 指数基础信息：`MarketIndexBasicInfo`，表名 `market_index_basic`。
5. 指数日线：`MarketIndexDailyData`，表名 `market_index_daily`。
6. 指数分钟线：`MarketIndexMinuteData`，表名 `market_index_minute`。
7. 当前模拟时间：`SystemSettings.current_mock_time` 和 `trade/time_utils.py`。

### 9.4 用户资产异常

1. 查 `users/models.py` 的 `UserProfile.update_asset_cache()`。
2. 查 `trade_position` 当前用户持仓。
3. 查 `trade_order` 当前用户 `status='filled'` 订单。
4. 查 `StockMinuteData` 是否有当前模拟时间之前价格。
5. 查 `DailyPerformance` 是否有昨日总资产作为日收益基准。

### 9.5 下单、持仓异常

1. 手工下单入口：`trade/views.py` 的 `PlaceOrderView.post`。
2. 持仓同步入口：`trade/views.py` 的 `sync_positions(user)`。
3. 订单表：`trade_order`。
4. 持仓表：`trade_position`。
5. 用户现金：`user_profile.balance`。
6. 注意：`sync_positions()` 只按成交订单校准股数，不重算均价。

### 9.6 策略不执行

1. `Strategy.status` 是否为 `active`。
2. `SystemSettings.current_mock_time` 是否落在 09:30-09:35 或 14:50-14:59。
3. `trade/scheduler.py` 是否启动并每秒执行 `clock_tick()`。
4. `trade/engine.py` 是否进入 `TradingEngine.run_all_active_strategies()`。
5. `trade/executor.py` 中 `strategy.code` 是否是合法 JSON。
6. `stock_pool` 是否为空，或 `__ALL__` 时 `StockBasicInfo`/`StockData` 是否有数据。

### 9.7 模拟时间不走

1. 查 `trade/apps.py` 的 `TradeConfig.ready()` 是否执行。
2. 查环境变量 `RUN_MAIN` 是否为 `true`。
3. 查 `trade/scheduler.py` 是否打印启动信息。
4. 查 `SystemSettings.time_speed` 是否大于 0。
5. 查 `django_apscheduler` 相关表和后台日志。

### 9.8 回测异常

1. 查请求区间内 `StockData` 是否有足够日线。
2. 查 `auth_user` 是否至少有一个用户。
3. 查 `backtest_task.status` 和 `error_message`。
4. 查 `backtest/engine.py` 的 Spark 初始化和 Java/PySpark 环境。
5. 查每只股票是否至少有足够交易日用于 5 日均线和下一日收益。

## 10. 已知依赖和运行前置条件

### 10.1 Python/Django 依赖

代码中可见依赖：

| 依赖 | 使用位置 |
| --- | --- |
| `django` | 整体后端 |
| `djangorestframework` | APIView、Response、TokenAuthentication |
| `django-cors-headers` | CORS |
| `django-apscheduler` | 调度器 job store |
| `mysqlclient` 或兼容 MySQL 驱动 | `ENGINE='django.db.backends.mysql'` |
| `apscheduler` | 模拟时间调度 |
| `pandas` | 数据下载、回测 Spark 输入 |
| `numpy` | 模拟数据、策略因子计算 |
| `pyspark` | 回测引擎 |
| `akshare` | 股票/指数数据下载 |
| `baostock` | 沪深 300 和分钟线下载 |
| `pytdx` | 指数分钟线下载 |
| `tqdm` | 数据导入命令进度条 |

仓库内未发现 `requirements.txt`。调试环境缺包时，需要根据 import 报错补装。

### 10.2 数据库和迁移

运行前需要：

1. MySQL 已启动，数据库 `quant_db` 可访问。
2. `settings.py` 中数据库账号密码正确。
3. 已执行 `python manage.py migrate`，包括 `rest_framework.authtoken`、`django_apscheduler` 和项目 apps。
4. 至少有行情基础数据，否则大部分行情、资产、回测接口会返回空或 0。
5. 需要登录接口可用时，`auth_user`、`authtoken_token` 表正常。

### 10.3 特别注意的已知问题

| 问题 | 影响 | 文件 |
| --- | --- | --- |
| `SystemControlView.get` 读取已删除字段 `skip_non_trading` | GET `/api/trade/control/` 可能 500 | `trade/views.py`、`trade/models.py`、`trade/migrations/0005...` |
| `managers.urls` 未挂载 | 管理 API 404 | `quant_backend/quant_backend/urls.py` |
| `run_scheduler` 管理命令引用不存在函数 | `python manage.py run_scheduler` 会失败 | `trade/management/commands/run_scheduler.py`、`trade/tasks.py` |
| `trade/apps.py` 备用调度方法引用不存在函数 | 调用 `TradeConfig.start_scheduler()` 会失败 | `trade/apps.py` |
| 数据导入命令部分会清空表 | 可能误删行情数据 | `stocks/management/commands/*.py` |
| 回测依赖 PySpark 和 Java | Windows 本地环境容易 Spark 初始化失败 | `backtest/engine.py` |
| `backtest` 使用 `User.objects.first()` | 回测不绑定当前请求用户，且无用户时直接失败 | `backtest/views.py` |

## 11. 快速接口索引

| App | 方法 | URL | View | 权限 |
| --- | --- | --- | --- | --- |
| stocks | GET | `/stocks/api/indices/` | `get_market_index_list_api` | 开放 |
| stocks | GET | `/stocks/api/index/<index_code>/` | `get_market_index_data_api` | 开放 |
| stocks | GET | `/stocks/api/data/<stock_code>/` | `get_stock_data_api` | 开放 |
| stocks | GET | `/stocks/api/market/` | `get_market_list_api` | 开放 |
| users | POST | `/api/users/login/`、`/users/api/login/` | `LoginView` | 开放 |
| users | POST | `/api/users/register/`、`/users/api/register/` | `RegisterView` | 开放 |
| users | GET | `/api/users/info/`、`/users/api/info/` | `UserInfoView` | Token |
| users | GET/POST/DELETE | `/api/users/favorites/`、`/users/api/favorites/` | `UserFavoriteView` | Token |
| trade | GET | `/api/trade/time/`、`/trade/api/time/` | `SystemTimeView` | Token |
| trade | GET | `/api/trade/performance/`、`/trade/api/performance/` | `PerformanceView` | Token |
| trade | POST | `/api/trade/transfer/`、`/trade/api/transfer/` | `FundTransferView` | Token |
| trade | GET/POST/DELETE | `/api/trade/strategy/`、`/trade/api/strategy/` | `StrategyView` | Token |
| trade | GET | `/api/trade/orders/`、`/trade/api/orders/` | `OrderListView` | Token |
| trade | POST | `/api/trade/place_order/`、`/trade/api/place_order/` | `PlaceOrderView` | Token |
| trade | GET | `/api/trade/positions/`、`/trade/api/positions/` | `PositionListView` | Token |
| trade | GET | `/api/trade/position/<stock_code>/`、`/trade/api/position/<stock_code>/` | `PositionDetailView` | Token |
| trade | GET/POST | `/api/trade/control/`、`/trade/api/control/` | `SystemControlView` | Token |
| managers | POST | 未挂载：`login/` | `AdminLoginView` | 逻辑校验 superuser |
| managers | GET | 未挂载：`dashboard/` | `DashboardStatsView` | Superuser Token |
| managers | GET | 未挂载：`users/` | `UserListView` | Superuser Token |
| backtest | POST | `/api/backtest/run/` | `RunBacktestView` | 开放 |
