# Frontend Debug Map

本文只描述 `quant_frontend` 的 Vue 前端结构，面向后续 agent 快速定位 UI、路由、接口和数据流问题。

## 项目入口与运行

- 前端目录：`quant_frontend`
- 技术栈：Vue 3、Vite、Vue Router 4、Pinia、Element Plus、axios、ECharts
- 应用入口：`src/main.js`
- 根组件：`src/App.vue`，仅渲染 `<RouterView />`
- 布局组件：`src/layout/MainLayout.vue`
- 路由入口：`src/router/index.js`
- Vite 配置：`vite.config.js`，当前只启用 `@vitejs/plugin-vue`，没有 devServer proxy

启动和构建命令：

- 安装依赖：在 `quant_frontend` 执行 `npm install`
- 本地启动：`npm run dev`，等价于 `vite`
- 生产构建：`npm run build`，等价于 `vite build`
- 本地预览构建产物：`npm run preview`，等价于 `vite preview`

调试注意：代码中接口多为硬编码 `http://127.0.0.1:8000/`，没有依赖 Vite proxy。若页面请求失败，先确认后端监听地址和浏览器 Network 面板中的实际 URL。

## 全局路由与鉴权

路由文件：`src/router/index.js`

路由结构：

- `/login` -> `src/views/LoginView.vue`
- `/register` -> `src/views/RegisterView.vue`
- `/` -> `src/layout/MainLayout.vue`，重定向到 `/dashboard`
- `/dashboard` -> `src/views/DashboardView.vue`
- `/market` -> `src/views/MarketView.vue`
- `/index/:code` -> `src/views/MarketIndexDetailView.vue`
- `/stock/:code` -> `src/views/StockDetailView.vue`
- `/backtest` -> `src/views/BacktestView.vue`

导航守卫：

- `router.beforeEach` 读取 `localStorage.getItem('token')`
- 未登录访问非登录/注册页会跳到 `login`
- 已登录访问任意路由直接放行，包括 `/login` 和 `/register`

布局组件 `MainLayout.vue`：

- 左侧菜单 index：`/dashboard`、`/market`、`/backtest`
- 子页面出口：内部 `<router-view v-slot="{ Component }">`
- 关键状态：`userInfo`、`activeMenu`
- 本地缓存：读取 `localStorage.user`，解析失败会删除 `user`
- 退出登录：`localStorage.clear()` 后跳转 `/login`

常见排查：

- 页面一刷新跳登录：检查 `localStorage.token` 是否存在，以及 token key 是否被登录/注册页写入一致。
- 侧边栏高亮异常：`activeMenu` 直接返回 `route.path`，详情页 `/stock/:code` 和 `/index/:code` 不对应菜单项。
- 用户名显示 Guest：检查 `localStorage.user` 是否是合法 JSON；`RegisterView.vue` 写的是 `userInfo`，`MainLayout.vue` 读的是 `user`。

## Axios 与接口调用分布

当前没有统一的 `src/api` 或请求拦截器模块。axios 调用分散在页面和组件中。

常见封装模式：

- 页面内 `axios.create({ baseURL: 'http://127.0.0.1:8000/', headers: { Authorization: 'Token ...' } })`
- 组件内临时 `getApi()` 返回 axios 实例
- 少数组件直接 `axios.get/post('http://127.0.0.1:8000/...')`
- `src/stores/user.js` 使用相对路径 `/api/users/info/`，但当前项目没有 Vite proxy，若直接调用可能指向前端域名

接口调用位置索引：

- 登录：`LoginView.vue` -> `POST http://127.0.0.1:8000/api/users/login/`
- 注册：`RegisterView.vue` -> `POST http://127.0.0.1:8000/api/users/register/`
- 用户信息：`DashboardView.vue`、`StockDetailView.vue` -> `GET api/users/info/`，失败后 fallback `users/api/info/`
- 用户信息 store：`stores/user.js` -> `GET /api/users/info/`
- 行情列表：`MarketView.vue` -> `GET stocks/api/market/?page=...`
- 自选股：`MarketView.vue` -> `GET/POST/DELETE api/users/favorites/`
- 大盘指数列表：`MarketIndexBoard.vue` -> `GET stocks/api/indices/`
- 大盘指数详情：`MarketIndexDetailView.vue` -> `GET stocks/api/index/:code/?freq=...&limit=1200`
- 股票行情详情：`StockDetailView.vue` -> `GET stocks/api/data/:code/?freq=min|daily`
- 单股持仓：`StockDetailView.vue` -> `GET api/trade/position/:code/`
- 下单：`TradePanel.vue` -> `POST api/trade/place_order/`
- 旧下单弹窗：`TradeDialog.vue` -> `POST api/trade/place_order/`，注意 payload 使用 `code` 而不是 `stock_code`
- 仪表盘订单：`DashboardView.vue` -> `GET trade/api/orders/`，失败后 fallback `api/trade/orders/`
- 交易时间：`DashboardView.vue` -> `GET trade/api/time/`
- 持仓列表：`PositionList.vue` -> `GET api/trade/positions/`
- 银证转账：`BankTransferDialog.vue` -> `POST trade/api/transfer/`
- 资产日线收益：`DailyPerformanceChart.vue` -> `GET trade/api/performance/?type=daily`
- 资产分时收益：`IntradayPerformanceChart.vue` -> `GET trade/api/performance/?type=intraday`
- 策略列表/保存/状态：`MyStrategies.vue` -> `GET/POST api/trade/strategy/`
- 策略删除：`MyStrategies.vue` -> `DELETE api/trade/strategy/`
- 回测运行：`BacktestView.vue` -> `POST http://127.0.0.1:8000/api/backtest/run/`
- 回测部署实盘策略：`BacktestView.vue` -> `POST api/trade/strategy/`

排查建议：

- 401/403：优先检查 Authorization header 是否为 `Token ${localStorage.token}`。
- 请求打到前端端口：查是否使用相对路径，例如 `stores/user.js`。
- 同一个接口有两种路径：优先看调用方是否有 fallback，例如订单和用户信息。
- CORS 或连接失败：当前无 proxy，浏览器必须能直连 `127.0.0.1:8000`。

## 登录页

路由：`/login`

组件文件：`src/views/LoginView.vue`

子组件关系：只使用 Element Plus 表单、输入框、按钮和图标，无业务子组件。

调用接口：

- `POST http://127.0.0.1:8000/api/users/login/`
- 请求体：`form`，包含 `username`、`password`
- 预期响应：`{ code: 200, data: { token, username } }`

关键状态变量：

- `loginFormRef`：Element Plus 表单引用
- `loading`：登录按钮 loading
- `form.username`、`form.password`
- `rules`：必填校验规则

数据流：

- 用户点击登录 -> `loginFormRef.validate` -> axios post 登录接口 -> 写入 `localStorage.token` 和 `localStorage.user` -> 跳转 `/dashboard`

常见排查：

- 登录后仍跳回登录：检查响应是否在 `res.data.data.token`，以及 `localStorage.token` 是否成功写入。
- 头部用户名不显示：`LoginView.vue` 写 `localStorage.user`，`MainLayout.vue` 读取该 key；确认值是 JSON 字符串。
- 按钮一直 loading：看 Network 请求是否挂起，或 catch/finally 是否执行。

## 注册页

路由：`/register`

组件文件：`src/views/RegisterView.vue`

子组件关系：只使用 Element Plus 表单、输入框、按钮和图标，无业务子组件。

调用接口：

- `POST http://127.0.0.1:8000/api/users/register/`
- 请求体：`username`、`phone`、`password`、`password_confirm`

关键状态变量：

- `registerFormRef`
- `loading`
- `form.username`、`form.phone`、`form.password`、`form.password_confirm`
- `rules`：用户名、手机号、密码校验

数据流：

- 表单校验 -> 本地确认两次密码一致 -> 注册接口 -> `code === 200` 后写入 `localStorage.token` 和 `localStorage.userInfo` -> 跳转 `/dashboard`

常见排查：

- 注册后布局显示 Guest：注册页写的是 `userInfo`，布局读的是 `user`。
- 注册后仍未登录：检查后端响应是否直接返回 `token`，当前代码读取的是 `res.data.token`，不是 `res.data.data.token`。
- 字段级报错：catch 中读取 `err.response.data.errors` 的第一个字段。

## 仪表盘 / 资产面板

路由：`/dashboard`

页面组件：`src/views/DashboardView.vue`

子组件关系：

- `AssetOverview.vue`：资产总览、系统时间、市场状态、打开银证转账
- `PerformanceChart.vue`：资产收益分析容器
- `DailyPerformanceChart.vue`：日线累计收益图，由 `PerformanceChart` 动态渲染
- `IntradayPerformanceChart.vue`：当日分时收益图，由 `PerformanceChart` 动态渲染
- `MyStrategies.vue`：实盘策略列表和参数设置
- `PositionList.vue`：当前持仓列表，对外暴露 `fetchData()`
- `RecentOrders.vue`：近期成交记录
- `BankTransferDialog.vue`：银证转账弹窗

调用接口：

- `GET api/users/info/`，失败后 `GET users/api/info/`
- `GET trade/api/orders/`，失败后 `GET api/trade/orders/`
- `GET trade/api/time/`
- 子组件 `PositionList.vue`：`GET api/trade/positions/`
- 子组件 `BankTransferDialog.vue`：`POST trade/api/transfer/`
- 子组件 `DailyPerformanceChart.vue`：`GET trade/api/performance/?type=daily`
- 子组件 `IntradayPerformanceChart.vue`：`GET trade/api/performance/?type=intraday`
- 子组件 `MyStrategies.vue`：`GET/POST/DELETE api/trade/strategy/`

关键状态变量：

- `loading`：首屏数据加载状态，但模板当前未直接使用
- `tableLoading`：近期成交表刷新 loading
- `timer`：3 秒轮询仪表盘数据
- `localTickTimer`：本地每秒推进系统时间显示
- `positionListRef`：调用持仓子组件 `fetchData()`
- `transferDialogVisible`：银证转账弹窗显示状态
- `systemTime`、`marketStatus`、`currentLocalTime`
- `userData`：资产对象，含 `total_assets`、`market_value`、`balance`、`withdrawable`、`daily_profit`、`total_profit`、`initial_capital`
- `recentOrders`

关键数据流：

- `onMounted` 调用 `fetchDashboardData()`，随后每 3 秒轮询。
- `fetchDashboardData()` 获取用户资产，计算 `total_profit = total_assets - initial_capital`。
- 同一函数获取近期订单和交易系统时间，并调用 `positionListRef.value.fetchData()` 刷新持仓。
- `localTickTimer` 基于最近一次后端时间每秒本地递增，避免每秒请求后端。
- `AssetOverview` 只消费父组件传入的 `userData`、`systemTime`、`marketStatus`，点击转账按钮向父组件发 `open-transfer`。
- `BankTransferDialog` 成功后发 `success`，父组件执行 `manualRefresh()`。

常见排查：

- 资产数值不更新：看 `DashboardView.vue` 的 `api/users/info/` 响应 `code` 是否为 200，且数据是否在 `data` 字段。
- 持仓不更新：确认 `positionListRef.value` 是否存在，以及 `PositionList.vue` 的 `api/trade/positions/` 是否返回 `data` 数组。
- 近期成交为空：检查 `trade/api/orders/` 和 fallback `api/trade/orders/` 哪个生效。
- 市场状态不对：`checkMarketStatus()` 基于字符串解析和固定 A 股交易时间判断，先看 `trade/api/time/` 的 `system_time` 格式。
- 分时收益显示休市遮罩：`IntradayPerformanceChart.vue` 中 `data.length === 0` 会设置 `isHoliday = true`。
- 图表宽度为 0：`DailyPerformanceChart.vue` 会延迟重试初始化；检查父容器是否被隐藏或尺寸为 0。

## 行情页

路由：`/market`

页面组件：`src/views/MarketView.vue`

子组件关系：

- `MarketIndexBoard.vue`：大盘指数卡片区，点击跳 `/index/:code`
- `MarketHeader.vue`：行情 tab 和手动刷新按钮
- `StockTable.vue`：股票列表、自选星标、排序、分页、跳转股票详情

调用接口：

- 行情列表：`GET stocks/api/market/?page=:page`
- 排序参数：`sort_prop`、`sort_order`
- 强制刷新参数：`refresh=true`
- 自选列表：`GET api/users/favorites/`
- 添加自选：`POST api/users/favorites/`，请求体 `{ code }`
- 删除自选：`DELETE api/users/favorites/`，请求体 `{ code }`
- 大盘指数子组件：`GET stocks/api/indices/`

关键状态变量：

- `activeTab`：`all` 或 `favorites`
- `tableData`：当前表格数据
- `marketTime`：取 `tableData[0].date`
- `loading`
- `total`
- `currentPage`
- `favoriteCodes`：`Set`，用于快速判断自选状态
- `refreshTimer`：3 秒轮询
- `tableRequestSeq`、`loadingRequestSeq`：防止旧请求覆盖新请求
- `sortProp`、`sortOrder`

关键数据流：

- 首次进入调用 `fetchMarketData(1)`，更新 `tableData`、`total`、`currentPage`、`marketTime`，随后静默刷新自选状态。
- `MarketHeader` 的 tab 变化触发 `handleTabChange()`，全市场走 `fetchMarketData()`，自选走 `fetchFavoritesList(true)`。
- `StockTable` 的排序事件触发 `handleSortChange()`，全市场请求后端排序，自选本地 `sortRows()`。
- `StockTable` 点击股票名称执行 `router.push('/stock/:code')`。
- `MarketIndexBoard` 独立请求大盘指数并跳转 `/index/:code`。
- 页面每 3 秒轮询，`all` tab 静默刷新行情，`favorites` tab 静默刷新自选表。

常见排查：

- 行情表空：检查 `stocks/api/market/` 响应是否有 `results` 和 `count`。
- 分页不生效：`StockTable.vue` 固定 `page-size=20`，父组件只传 `page`，看后端分页大小是否一致。
- 排序无效：全市场依赖后端识别 `sort_prop`/`sort_order`；自选只按当前前端数组排序。
- 自选状态不准：检查 `api/users/favorites/` 返回项是否有 `stock` 字段，前端用 `list.map(item => item.stock)`。
- 切换 tab 后数据跳变：看 `tableRequestSeq` 是否因并发请求被后发请求覆盖；Network 中确认哪个请求最后返回。
- 指数卡片不显示：排查 `MarketIndexBoard.vue` 的 `stocks/api/indices/`，要求响应 `code === 200` 且 `data` 为数组。

## 股票详情页与交易面板

路由：`/stock/:code`

页面组件：`src/views/StockDetailView.vue`

子组件关系：

- `StockHeader.vue`：返回按钮、股票名称/代码、分时/日K切换
- `StockChart.vue`：根据 `freq` 分派图表
- `StockMinuteChart.vue`：分时 K 线和成交量 ECharts
- `StockDailyChart.vue`：日 K 线和成交量 ECharts
- `TradePanel.vue`：买入/卖出下单面板

调用接口：

- 行情报价：`GET stocks/api/data/:code/?freq=min`
- 图表数据：`GET stocks/api/data/:code/?freq=min|daily`
- 用户余额：`GET api/users/info/`，失败后 `GET users/api/info/`
- 单股持仓：`GET api/trade/position/:code/`
- 下单：`TradePanel.vue` -> `POST api/trade/place_order/`，请求体 `stock_code`、`direction`、`price`、`volume`

关键状态变量：

- `stockCode`：来自 `route.params.code`
- `stockName`
- `systemTimeDisplay`
- `chartData`
- `chartLoading`
- `viewMode`：`min` 或 `daily`
- `latestPrice`
- `userBalance`
- `userPosition`
- `refreshTimer`：2 秒轮询
- `TradePanel` 内部：`tradeDirection`、`tradePrice`、`tradeVolume`、`loading`

关键数据流：

- `onMounted` 同时调用 `fetchQuote()`、`fetchChartData()`、`fetchUserAssets()`。
- `fetchQuote()` 固定请求分时数据，取最后一条 `close` 作为 `latestPrice`，并更新 `stockName` 和 `systemTimeDisplay`。
- `fetchChartData()` 按 `viewMode` 请求图表数据，传给 `StockChart`。
- `StockChart` 在 `freq === 'min' || freq === '5min'` 渲染 `StockMinuteChart`，`freq === 'daily'` 渲染 `StockDailyChart`。
- `TradePanel` 监听 `latestPrice` 和 `userBalance`，自动填充市价和默认 100 股买入量。
- 下单成功后 `TradePanel` 发 `trade-success`，父组件调用 `fetchUserAssets()` 刷新余额和单股持仓。
- 页面每 2 秒刷新报价；仅在 `viewMode === 'min'` 时静默刷新图表。

常见排查：

- 标题一直“加载中”：看 `stocks/api/data/:code/?freq=min` 是否返回 `code === 200` 和 `name`。
- 最新价为 0：检查 `data` 数组最后一项是否有 `close` 且可 `parseFloat`。
- 图表空白：确认 `chartData` 数组字段包含 `date`、`open`、`close`、`low`、`high`、`volume`。
- 日 K 切换无效：`StockHeader.vue` 发 `update:viewMode`，父组件同时使用 `v-model:view-mode` 和 `@update:view-mode`；检查事件名是否被 Vue 正确映射到 `viewMode`。
- 买入按钮禁用：`TradePanel.vue` 判断 `userBalance < latestPrice * 100`，先看余额和价格是否为数值。
- 下单失败：`TradePanel.vue` payload 字段是 `stock_code`；如果后端只认 `code`，参照未挂载的 `TradeDialog.vue` 中使用的是 `code`。
- 卖出数量异常：`setVolume(1.0)` 对卖出使用全部 `userPosition`，其他比例按 100 股取整。

## 大盘指数详情页

路由：`/index/:code`

页面组件：`src/views/MarketIndexDetailView.vue`

子组件关系：

- `StockChart.vue`
- `StockMinuteChart.vue`
- `StockDailyChart.vue`

调用接口：

- `GET stocks/api/index/:code/?freq=min|daily&limit=1200`

关键状态变量：

- `indexCode`：来自 `route.params.code`
- `indexName`
- `latestPrice`
- `latestTime`
- `chartData`
- `chartLoading`
- `viewMode`
- `refreshTimer`：10 秒轮询

关键数据流：

- `onMounted` 调用 `fetchIndexData()`。
- `fetchIndexData()` 按 `viewMode` 请求指数数据，更新名称、图表数组、最新点位和时间。
- 切换 `viewMode` 时先清空 `chartData`，再重新请求。
- 仅分时模式 `min` 下每 10 秒静默刷新。
- 图表复用股票图表组件，因此指数数据字段结构也要满足 K 线组件字段要求。

常见排查：

- 指数详情 404：确认从 `MarketIndexBoard.vue` 传入的 `item.code` 是否与后端 `stocks/api/index/:code/` 匹配。
- 最新点位显示 0：看响应字段是否是 `latest_price`。
- 时间不显示：看响应字段是否是 `latest_time`。
- 图表不显示：检查 `data` 数组字段是否与 `StockMinuteChart`/`StockDailyChart` 需要的字段一致。
- 切换日线仍轮询：代码只在 `viewMode === 'min'` 时轮询，如果 Network 仍请求 daily，检查是否是手动切换触发。

## 回测页

路由：`/backtest`

页面组件：`src/views/BacktestView.vue`

子组件关系：无业务子组件，页面内部直接使用 Element Plus 表单、表格、ECharts。

调用接口：

- 运行回测：`POST http://127.0.0.1:8000/api/backtest/run/`
- 部署实盘策略：`POST api/trade/strategy/`

关键状态变量：

- `defaultForm`：默认策略参数
- `defaultDateRange`
- `form`：`task_name`、`initial_capital`、`weight_mom`、`weight_bias`、`top_n`
- `dateRange`
- `loading`
- `resultData`
- `chartRef`
- `myChart`

本地缓存：

- `quant_backtest_form`
- `quant_backtest_dateRange`

关键数据流：

- 表单参数通过 `watch` 持久化到 localStorage。
- `runBacktest()` 校验日期范围 -> 组装 payload -> 请求回测接口 -> `resultData = response.data.data` -> `nextTick(renderChart)`。
- 结果卡片读取 `resultData.total_return`、`annualized_return`、`final_capital`、`equity_curve`、`trade_records`。
- `deployToRealTrade()` 将多因子参数 JSON 化到 `code` 字段，默认 `stock_pool: 'sz.300394'`，保存成功后跳 `/dashboard`。

常见排查：

- 点击无反应：先检查 `dateRange` 是否为长度 2 的数组。
- 回测结果报字段错误：模板直接调用 `resultData.final_capital.toFixed(2)` 和 `resultData.equity_curve.length`，后端字段缺失会渲染报错。
- 图表不显示：确认 `equity_curve` 每项有 `date`、`equity`、`daily_return`。
- 参数恢复异常：清理 localStorage 中 `quant_backtest_form` 和 `quant_backtest_dateRange` 后重试。
- 部署后策略不出现：看 `api/trade/strategy/` 响应 `code` 是否为 200，并到 `DashboardView.vue` 的 `MyStrategies.vue` 排查列表接口。

## 实盘策略组件

挂载页面：`/dashboard` 的 `DashboardView.vue`

组件文件：`src/components/MyStrategies.vue`

调用接口：

- `GET api/trade/strategy/` 获取策略列表
- `POST api/trade/strategy/` 新建/更新策略或切换状态
- `DELETE api/trade/strategy/` 删除策略，请求体 `{ id }`

关键状态变量：

- `strategies`
- `loading`
- `saving`
- `dialogVisible`
- `currentStrategy`
- `ALL_STOCK_SENTINEL = '__ALL__'`
- `ALL_STOCK_LABEL = '全部股票'`

数据流：

- `onMounted(fetchStrategies)` 拉取策略。
- 表格 switch 直接修改 `row.status`，再请求保存；失败时反转回原状态。
- 打开弹窗时将 `row.code` 解析为 JSON，映射多因子权重。
- 保存时将权重写入 `code` JSON 字符串，股票池使用英文逗号规整，全部股票用 `__ALL__`。

常见排查：

- 多因子参数显示 0：`parseConfig(row.code)` JSON 解析失败。
- 全部股票显示异常：检查后端返回 `stock_pool` 是否为 `__ALL__`、`ALL`、`ALL_STOCKS`、`全部` 或 `全部股票`。
- 状态切换闪回：看 `POST api/trade/strategy/` 是否返回 `code === 200`。
- 保存后列表没变：`saveStrategy()` 成功后调用 `fetchStrategies()`；看列表接口是否返回最新数据。

## 图表组件通用排查

股票/指数 K 线图：

- 入口组件：`StockChart.vue`
- 分时组件：`StockMinuteChart.vue`
- 日线组件：`StockDailyChart.vue`
- 输入 props：`data` 数组、`freq`
- 必需数据字段：`date`、`open`、`close`、`low`、`high`、`volume`

排查点：

- 容器高度：父组件必须给图表容器高度，股票详情为 450px，指数详情为 540px，图表自身 `.echart-box` 为 480px。
- 空数据：两个 K 线组件都会显示“暂无数据”。
- resize：组件内部 addEventListener，但匿名 resize 监听没有在销毁时移除；如排查内存问题可关注重复挂载。
- dataZoom：分时图会尽量保持用户缩放位置，日线图只首次初始化默认显示最近 60 条。

资产收益图：

- 容器组件：`PerformanceChart.vue`
- 日线：`DailyPerformanceChart.vue`
- 分时：`IntradayPerformanceChart.vue`
- 日线接口字段：`date`、`total_return_rate`
- 分时接口字段：`time`、`total_return_rate`

排查点：

- `PerformanceChart.vue` 使用 `keep-alive`，切换 tab 不一定重新挂载。
- 分时图 2 秒轮询，空数组会显示休市遮罩。
- 日线图初始化时如果宽度为 0，会 50ms 后重试。

## 未挂载或低使用组件

- `src/components/TradeDialog.vue`：旧交易弹窗组件，当前路由页面未发现挂载。它调用 `api/trade/place_order/`，payload 字段为 `code`。
- `src/components/HelloWorld.vue`：Vite 示例组件，当前未挂载。
- `src/stores/user.js`：定义了 Pinia user store，但当前主要页面直接读写 localStorage 和 axios，未在已读页面中发现实际使用。

调试时不要优先修改这些文件，除非先确认实际挂载路径或调用方。

## 页面级排查速查

- 白屏：先看浏览器 Console 是否是模板字段空值报错；回测页最容易因 `resultData` 字段缺失触发。
- 路由进不去：看 `router.beforeEach` 和 `localStorage.token`。
- 请求全部失败：确认后端 `127.0.0.1:8000`、CORS、Token header。
- 某页面轮询频繁：行情页 3 秒，股票详情 2 秒，仪表盘 3 秒，资产分时 2 秒，指数详情 10 秒。
- 数据闪烁或被旧数据覆盖：行情页有 request seq 防护；其他页面没有，需看 Network 返回顺序。
- 字段对不上：前端多处要求 `res.data.code === 200`，且数据字段名是硬编码。
- 金额/涨跌颜色：项目约定红色上涨、绿色下跌；排查 UI 颜色时看各组件的 `getPriceClass` 或 `getChangeClass`。
