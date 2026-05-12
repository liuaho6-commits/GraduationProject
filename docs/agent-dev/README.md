# Agent 开发文档入口

本目录用于后续 agent 快速理解项目、定位问题和选择调试路线。先读本文件，再按任务类型进入对应专题文档。

## 文档地图

| 文档 | 用途 |
| --- | --- |
| [01_project_overview.md](01_project_overview.md) | 项目总览、前后端入口、主要 API、已知不一致 |
| [02_backend_api.md](02_backend_api.md) | Django app 分工、URL、权限、接口输入输出、后端依赖 |
| [03_market_data_debug.md](03_market_data_debug.md) | 股票/指数行情、K 线、模拟时间过滤、数据导入脚本 |
| [04_trade_time_debug.md](04_trade_time_debug.md) | 模拟时间、交易、订单、持仓、收益、策略撮合 |
| [05_frontend_debug.md](05_frontend_debug.md) | Vue 路由、页面组件、接口调用、图表和 UI 排查 |
| [06_database_dataflow.md](06_database_dataflow.md) | 数据库模型、核心数据流、导入命令、表级排查 |
| [07_troubleshooting.md](07_troubleshooting.md) | 常见故障现象、排查步骤、可验证命令 |

## 推荐阅读路线

### 调行情问题

1. [03_market_data_debug.md](03_market_data_debug.md)：先确认接口、模拟时间、日线/分钟线过滤和前端展示链路。
2. [06_database_dataflow.md](06_database_dataflow.md)：再查行情表、指数表、导入脚本和数据范围。
3. [05_frontend_debug.md](05_frontend_debug.md)：如果后端接口有数据但页面不显示，查行情页、股票详情页、指数详情页和图表组件。
4. [07_troubleshooting.md](07_troubleshooting.md)：参考“行情日期不对”“股票或指数 K 线为空”。

### 调交易问题

1. [04_trade_time_debug.md](04_trade_time_debug.md)：先看模拟时间、手动下单、策略撮合、持仓和收益计算。
2. [02_backend_api.md](02_backend_api.md)：核对交易 API 路径、权限、请求体和返回结构。
3. [06_database_dataflow.md](06_database_dataflow.md)：查 `Order`、`TradeRecord`、`Position`、`UserProfile`、收益表的数据关系。
4. [05_frontend_debug.md](05_frontend_debug.md)：如果是页面下单或策略保存异常，查 `TradePanel.vue`、`MyStrategies.vue`、仪表盘组件。

### 调前端问题

1. [05_frontend_debug.md](05_frontend_debug.md)：先定位路由、页面、组件、接口调用和 localStorage/Token 行为。
2. [02_backend_api.md](02_backend_api.md)：核对后端真实 URL、权限和响应结构。
3. [03_market_data_debug.md](03_market_data_debug.md) 或 [04_trade_time_debug.md](04_trade_time_debug.md)：按页面业务类型继续查行情或交易。
4. [07_troubleshooting.md](07_troubleshooting.md)：参考接口失败、登录/Token、依赖缺失等通用故障。

### 调数据库问题

1. [06_database_dataflow.md](06_database_dataflow.md)：先看模型表名、字段、约束、读写位置和核心数据流。
2. [02_backend_api.md](02_backend_api.md)：确认接口依赖哪些模型、权限和前置数据。
3. [03_market_data_debug.md](03_market_data_debug.md)：行情数据缺失、重复、时间范围问题优先读这里。
4. [04_trade_time_debug.md](04_trade_time_debug.md)：交易数据、资产缓存、收益表和模拟时间问题优先读这里。

### 调启动/依赖问题

1. [07_troubleshooting.md](07_troubleshooting.md)：先按后端启动、前端请求、数据库连接、依赖缺失章节做验证。
2. [01_project_overview.md](01_project_overview.md)：确认前端、后端、调度器和依赖现状。
3. [02_backend_api.md](02_backend_api.md)：查 Django 设置、URL、认证、依赖和迁移前置条件。
4. [05_frontend_debug.md](05_frontend_debug.md)：查前端启动脚本、Vite 配置和硬编码后端地址。

## 已收敛结论

- 当前文档以 `docs/agent-dev/` 内专题文档为准；根 `README.md`、`项目设计.md` 和后端旧说明可作为背景资料，但可能滞后。
- 模拟时间主来源是数据库 `SystemSettings.current_mock_time`，不是 `quant_backend/mock_time.json`。
- 策略调度当前更可信路径是 `TradeConfig.ready()` 自动调用 `trade.scheduler.start_scheduler()`，`python manage.py run_scheduler` 是疑似失效旧入口。
- `Strategy.code` 当前按 JSON 多因子参数使用，不是旧设计里的用户 Python 策略沙箱。
- 前端没有统一 API 客户端和 Vite proxy，多数请求硬编码或拼接到 `http://127.0.0.1:8000/`。
- 后端 Python 依赖没有标准清单，排查环境问题时先按 import 和报错确认缺包。

## 整合检查结论

### 明显重复

- 模拟时间、`SystemSettings.current_mock_time`、`mock_time.json` 非主路径在多份文档中重复出现，但结论一致。
- `run_scheduler` 旧入口、`skip_non_trading` 已删除字段、`managers.urls` 未挂载在多份文档中重复出现，作为高风险已知问题保留是有价值的。
- 行情接口和交易接口索引在 [01_project_overview.md](01_project_overview.md)、[02_backend_api.md](02_backend_api.md)、专题调试文档中都有覆盖，README 只做导航，不再复制完整接口表。

### 已处理或仍需关注的矛盾

- 已修正 [07_troubleshooting.md](07_troubleshooting.md) 中关于 `python manage.py run_scheduler` 的旧说法；当前统一表述为该命令是疑似失效旧入口，调度问题优先核对 `trade/apps.py`、`trade/scheduler.py`、`trade/tasks.py`。
- 根 README、旧设计文档与当前专题文档存在机制差异，例如 `mock_time.json`、Python 策略沙箱、`run_scheduler`。本目录文档以当前源码梳理为准。

### 待补文档缺口

| 缺口 | 影响 | 建议补充位置 |
| --- | --- | --- |
| Python 依赖清单缺失 | 新环境启动只能靠报错补包，回测和调度问题难复现 | 新增 `docs/agent-dev/08_environment.md` 或项目级依赖文件 |
| 数据初始化步骤不完整 | agent 可能误运行清表命令，或不知道最小数据集要求 | 在 [06_database_dataflow.md](06_database_dataflow.md) 增加“安全初始化流程” |
| 接口契约没有单一索引 | 前端字段、后端响应、权限分散，容易修错调用方 | 在 [02_backend_api.md](02_backend_api.md) 增加“接口契约速查表” |
| 调度器现状未单独收口 | `runserver` 自动调度和旧 `run_scheduler` 容易混淆 | 在 [04_trade_time_debug.md](04_trade_time_debug.md) 增加“调度器判定流程” |
| 验收命令缺少统一清单 | 修改后不知道最小验证哪些路径 | 在本 README 增加“最小验证清单”或新增 `09_verification.md` |
| 部署说明缺失 | 生产环境 API 地址、CORS、MySQL、Spark/Java、调度器行为不明确 | 新增部署文档，或在 [07_troubleshooting.md](07_troubleshooting.md) 增加部署风险 |

## 最小验证清单

文档类改动不要求跑业务命令。若后续 agent 修改代码，建议至少按改动范围选用以下验证：

| 改动范围 | 建议验证 |
| --- | --- |
| 后端配置/API | 在 `quant_backend` 执行 `python manage.py check`，并请求相关接口 |
| 前端页面/组件 | 在 `quant_frontend` 执行 `npm run build`，再人工检查对应页面 Network 和 Console |
| 行情逻辑 | 验证 `/stocks/api/market/`、`/stocks/api/data/<code>/?freq=min`、模拟时间和数据库数据范围 |
| 交易逻辑 | 验证 `/api/trade/place_order/`、`/api/trade/positions/`、`/api/users/info/`，并检查 `Order`、`Position`、`UserProfile` |
| 收益/时间逻辑 | 验证 `/trade/api/time/`、`/trade/api/performance/?type=daily`、`type=intraday`，并检查 `SystemSettings` |
| 回测逻辑 | 验证 `/api/backtest/run/`，同时确认 Java、PySpark、`StockData` 和至少一个 Django 用户存在 |

## 后续待办项

- 补充后端依赖清单，至少覆盖 Django、DRF、CORS、APScheduler、MySQL 驱动、Pandas、Numpy、PySpark、AkShare、Baostock、pytdx、tqdm。
- 明确调度器唯一推荐启动方式，并处理旧 `run_scheduler` 文档或命令。
- 增加数据库安全初始化流程，清楚标记“只读检查”“会清空表”“会按范围覆盖”。
- 把接口路径、权限、请求体、响应字段、前端调用位置整理为一个可搜索索引。
- 补充部署/运行环境说明，包括 API 地址、CORS、MySQL、Java/Spark、定时任务和生产启动方式。
- 核实并整理旧文档差异，避免后续 agent 被旧机制误导。
