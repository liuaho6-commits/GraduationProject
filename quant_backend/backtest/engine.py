import os
import sys
import pandas as pd
from datetime import datetime

# 确保 Windows 下 Pandas 与 PySpark 的兼容性
if not hasattr(pd.DataFrame, 'iteritems'):
    pd.DataFrame.iteritems = pd.DataFrame.items

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lag, lead, round as spark_round, stddev, avg, lit, coalesce
from pyspark.sql.window import Window

from stocks.models import StockData
from trade.factor_config import normalize_strategy_config, get_enabled_factors


class SparkBacktestEngine:
    def __init__(self, task_id=None):
        self.task_id = task_id
        self._init_spark()

    def _init_spark(self):
        os.environ['PYSPARK_PYTHON'] = sys.executable
        os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
        os.environ['SPARK_LOCAL_IP'] = '127.0.0.1'

        self.spark = SparkSession.builder \
            .appName(f"QuantBacktest_Task_{self.task_id if self.task_id else 'Debug'}") \
            .master("local[*]") \
            .config("spark.driver.host", "127.0.0.1") \
            .config("spark.driver.bindAddress", "127.0.0.1") \
            .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
            .getOrCreate()
        self.spark.sparkContext.setLogLevel("ERROR")

    def load_data(self, start_date, end_date):
        qs = StockData.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).values('date', 'code', 'close')

        pdf = pd.DataFrame.from_records(qs)
        if pdf.empty:
            raise ValueError(f"在 {start_date} 至 {end_date} 期间没有股票数据！")

        pdf['date'] = pd.to_datetime(pdf['date']).dt.strftime('%Y-%m-%d')
        return self.spark.createDataFrame(pdf)

    def compute_multi_factors(self, sdf, weight_mom=0.5, weight_bias=0.5, config=None):
        """核心业务逻辑：计算内置多因子并截面打分"""
        strategy_config = normalize_strategy_config(
            config,
            legacy_params={"weight_mom": weight_mom, "weight_bias": weight_bias} if config is None else None
        )
        enabled_factors = get_enabled_factors(strategy_config)
        if not enabled_factors:
            raise ValueError("至少需要启用一个权重非零的因子")

        ts_window = Window.partitionBy("code").orderBy("date")
        ts_window_5d = Window.partitionBy("code").orderBy("date").rowsBetween(-4, 0)
        ts_window_20d = Window.partitionBy("code").orderBy("date").rowsBetween(-19, 0)

        # 1. 时序计算：内置因子与 T+1 日收益率
        sdf_factors = sdf.withColumn("pre_close", lag("close", 1).over(ts_window)) \
            .withColumn("daily_return", (col("close") - col("pre_close")) / col("pre_close")) \
            .withColumn("next_return", lead("daily_return", 1).over(ts_window)) \
            .withColumn("close_5", lag("close", 5).over(ts_window)) \
            .withColumn("close_20", lag("close", 20).over(ts_window)) \
            .withColumn("ma_5", avg("close").over(ts_window_5d)) \
            .withColumn("ma_20", avg("close").over(ts_window_20d)) \
            .withColumn("vol_20_raw", stddev("daily_return").over(ts_window_20d)) \
            .withColumn("factor_mom_20", (col("close") - col("close_20")) / col("close_20")) \
            .withColumn("factor_rev_5", -((col("close") - col("close_5")) / col("close_5"))) \
            .withColumn("factor_vol_20", -col("vol_20_raw")) \
            .withColumn("factor_trend_20", (col("close") - col("ma_20")) / col("ma_20")) \
            .withColumn("factor_mom_1", col("daily_return")) \
            .withColumn("factor_bias_5", (col("close") - col("ma_5")) / col("ma_5"))

        required_condition = None
        for item in enabled_factors:
            factor_col = col(f"factor_{item['code']}").isNotNull()
            required_condition = factor_col if required_condition is None else required_condition & factor_col

        if required_condition is not None:
            sdf_factors = sdf_factors.filter(required_condition)

        # 2. 截面 Z-Score 标准化
        cs_window = Window.partitionBy("date")
        sdf_zscore = sdf_factors
        score_expr = lit(0.0)
        for item in enabled_factors:
            code = item["code"]
            weight = float(item["weight"])
            factor_col = f"factor_{code}"
            avg_col = f"{code}_avg"
            std_col = f"{code}_std"
            z_col = f"z_{code}"

            sdf_zscore = sdf_zscore \
                .withColumn(avg_col, avg(factor_col).over(cs_window)) \
                .withColumn(std_col, coalesce(stddev(factor_col).over(cs_window), lit(0.0))) \
                .withColumn(z_col, (col(factor_col) - col(avg_col)) / (col(std_col) + lit(1e-6)))

            score_expr = score_expr + col(z_col) * lit(weight)

        # 3. 综合打分
        sdf_final = sdf_zscore.withColumn("total_score", spark_round(score_expr, 4))
        return sdf_final

    def simulate_strategy(self, factor_df, top_n=2, config=None):
        """根据每日综合打分取 Top N，并扣除换手手续费生成资金曲线"""
        strategy_config = normalize_strategy_config(
            {"weight_mom": 1.0, "weight_bias": 0.0, "top_n": top_n} if config is None else config
        )
        top_n = int(strategy_config["top_n"])
        buy_threshold = float(strategy_config["buy_threshold"])
        allow_cash = bool(strategy_config["allow_cash"])
        fee_rate = float(strategy_config["fee_rate"])

        pdf = factor_df.select("date", "code", "close", "next_return", "total_score").toPandas()
        if pdf.empty:
            return pd.DataFrame()

        pdf["date"] = pd.to_datetime(pdf["date"])
        pdf = pdf.dropna(subset=["total_score"]).sort_values(["date", "total_score"], ascending=[True, False])
        dates = sorted(pdf["date"].dt.strftime("%Y-%m-%d").unique())
        if len(dates) < 2:
            return pd.DataFrame()

        holdings = []
        weights = {}
        records = []

        for index, signal_date in enumerate(dates[:-1]):
            return_date = dates[index + 1]
            day_df = pdf[pdf["date"].dt.strftime("%Y-%m-%d") == signal_date].copy()
            day_df = day_df.sort_values(["total_score", "code"], ascending=[False, True]).reset_index(drop=True)
            day_df["rank"] = day_df.index + 1
            day_df["code_price"] = day_df.apply(lambda row: f"{row['code']}:{float(row['close']):.2f}", axis=1)

            candidates = day_df[day_df["rank"] <= top_n]
            if allow_cash:
                candidates = candidates[candidates["total_score"] >= buy_threshold]

            next_holdings = candidates["code"].head(top_n).tolist()
            next_weights = {code: 1 / len(next_holdings) for code in next_holdings} if next_holdings else {}
            all_weight_codes = set(weights) | set(next_weights)
            turnover = sum(abs(next_weights.get(code, 0.0) - weights.get(code, 0.0)) for code in all_weight_codes)

            holdings = next_holdings
            weights = next_weights

            if holdings:
                held_df = day_df[day_df["code"].isin(holdings)]
                valid_returns = held_df["next_return"].dropna()
                gross_return = float(valid_returns.mean()) if not valid_returns.empty else 0.0
                buy_stocks = held_df["code_price"].tolist()
            else:
                gross_return = 0.0
                buy_stocks = []

            portfolio_return = gross_return - turnover * fee_rate
            records.append({
                "date": return_date,
                "portfolio_return": round(portfolio_return, 4),
                "gross_return": round(gross_return, 4),
                "turnover": round(turnover, 4),
                "holdings_count": len(holdings),
                "buy_stocks": buy_stocks,
            })

        pdf_returns = pd.DataFrame(records)
        if pdf_returns.empty:
            return pdf_returns

        pdf_returns["equity"] = (1 + pdf_returns["portfolio_return"]).cumprod()
        return pdf_returns

    def stop(self):
        if self.spark:
            self.spark.stop()
