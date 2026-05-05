# 沪深300行情数据下载与连续性校验

这个目录独立于项目原有的 `raw_data`，用于下载、保存、清洗和校验沪深300日线与5分钟线。

## 数据目录

脚本运行后会自动创建：

- `data/basic/hs300_components.csv`：沪深300成分股列表
- `data/raw/daily/`：原始日线
- `data/raw/minute5/`：原始5分钟线
- `data/clean/daily/`：已修正并校验的日线
- `data/clean/minute5/`：已修正并校验的5分钟线
- `data/reports/validation_report.csv`：校验汇总报告
- `data/reports/validation_report.json`：校验明细报告

## 规则说明

真实市场行情允许隔夜跳空，所以日线不要求“今日开盘价等于昨日收盘价”。5分钟线只要求同一交易日内连续，每天第一根K线允许跳空。本目录的交付数据采用两层保存：

1. `raw` 保留数据源原始结果，方便追溯。
2. `clean` 保留日线原始开盘价，只修正 OHLC 边界；5分钟线从每天第二根开始，将 `open` 修正为上一根5分钟K线的 `close`，并同步扩展 `high/low`，保证 OHLC 自洽。

校验规则：

- 日线：允许不连续，只校验 OHLC 自洽
- 5分钟线：同一天内第 N 根5分钟K线 `open == 第 N-1 根5分钟K线 close`；每天第一根不校验连续性
- `high >= max(open, close)`
- `low <= min(open, close)`

## 先跑样例

在项目根目录运行：

```powershell
python .\hs300_data_center\hs300_pipeline.py sample
```

样例会下载几只股票的小范围数据，生成 clean 文件，并输出校验报告。

## 下载全量沪深300

```powershell
python .\hs300_data_center\hs300_pipeline.py run --daily-start 2020-01-01 --minute-start 2026-03-18 --end 2026-04-30
```

说明：

- `run` 默认下载沪深300全部成分股。
- `--daily-start` 控制日线起始日期。
- `--minute-start` 控制5分钟线起始日期。
- 当前默认数据源为东方财富；它的5分钟线通常只返回较近一段历史。若报告里出现 `raw_min_date` 晚于你指定的 `--minute-start`，说明数据源没有返回更早的5分钟线。

## 2023-2026 采样结论

已用 `sh.600000`、`sz.000001`、`sz.300750` 采样验证：

- 东方财富日线可以拿到 `2023-01-03` 到 `2026-04-30`，每只样本约 804 行。
- 东方财富5分钟线即使指定 `2023-01-01` 到 `2026-04-30`，也只返回 `2026-03-18 09:35` 到 `2026-04-30 15:00`，每只样本 1488 行。
- Baostock 理论上更适合长周期分钟线，但当前环境登录失败：`10002007 网络接收错误`。
- TDX/通达信公共服务器可以分页取分钟线，但本次可连服务器最早只到 `2024-04-19`，仍不能覆盖 2023。
- AKShare `1.18.60` 已采样：
  - `stock_zh_a_hist` 日线可以拿到 `2023-01-03` 到 `2026-04-30`。
  - `stock_zh_a_hist_min_em(period="5")` 与东方财富直接接口一致，只返回 `2026-03-18 09:35` 到 `2026-04-30 15:00`，每只样本 1488 行。
  - `stock_zh_a_minute(period="5")` 无 start/end 参数，返回最近约 1970 根，样本最早为 `2026-03-03 14:55`，仍不能覆盖 2023。

因此，当前已接入的免费公开源可以满足 2023-2026 日线；5分钟线无法完整覆盖 2023-2026，需要接入可提供历史分钟线的稳定数据源，例如可用的 Baostock 网络环境、Tushare Pro Token、JoinQuant/RiceQuant 导出数据，或购买/导入本地历史分钟数据。

## 常用参数

只下载前 10 只股票试跑：

```powershell
python .\hs300_data_center\hs300_pipeline.py run --limit 10 --daily-start 2026-01-01 --minute-start 2026-04-20 --end 2026-04-30
```

指定股票试跑：

```powershell
python .\hs300_data_center\hs300_pipeline.py run --codes sh.600000,sz.000001,sz.300750 --daily-start 2026-01-01 --minute-start 2026-04-20 --end 2026-04-30
```

只校验已有文件：

```powershell
python .\hs300_data_center\hs300_pipeline.py validate
```

强制重新下载：

```powershell
python .\hs300_data_center\hs300_pipeline.py run --force
```
