import os
import sys
import pandas as pd
from datetime import datetime

# 确保 Windows 下 Pandas 与 PySpark 的兼容性
if not hasattr(pd.DataFrame, 'iteritems'):
    pd.DataFrame.iteritems = pd.DataFrame.items

from pyspark.sql import SparkSession
# 🟢 修复核心：引入 concat_ws 用于拼接字符串
from pyspark.sql.functions import col, lag, lead, round, mean, stddev, avg, rank, collect_list, concat_ws
from pyspark.sql.window import Window

from stocks.models import StockData


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

    def compute_multi_factors(self, sdf, weight_mom=0.5, weight_bias=0.5):
        """核心业务逻辑：计算多因子并截面打分"""
        ts_window = Window.partitionBy("code").orderBy("date")
        ts_window_5d = Window.partitionBy("code").orderBy("date").rowsBetween(-4, 0)

        # 1. 时序计算：动量、均线偏离度，以及获取 T+1 日收益率
        sdf_factors = sdf.withColumn("pre_close", lag("close", 1).over(ts_window)) \
            .withColumn("daily_return", (col("close") - col("pre_close")) / col("pre_close")) \
            .withColumn("next_return", lead("daily_return", 1).over(ts_window)) \
            .withColumn("factor_momentum", col("daily_return")) \
            .withColumn("ma_5", avg("close").over(ts_window_5d)) \
            .withColumn("factor_bias", (col("close") - col("ma_5")) / col("ma_5"))

        sdf_factors = sdf_factors.filter(col("factor_bias").isNotNull() & col("factor_momentum").isNotNull())

        # 2. 截面 Z-Score 标准化 (矩阵优化核心)
        cs_window = Window.partitionBy("date")
        sdf_zscore = sdf_factors \
            .withColumn("mom_avg", avg("factor_momentum").over(cs_window)) \
            .withColumn("mom_std", stddev("factor_momentum").over(cs_window)) \
            .withColumn("bias_avg", avg("factor_bias").over(cs_window)) \
            .withColumn("bias_std", stddev("factor_bias").over(cs_window)) \
            .withColumn("z_momentum", (col("factor_momentum") - col("mom_avg")) / (col("mom_std") + 1e-6)) \
            .withColumn("z_bias", (col("factor_bias") - col("bias_avg")) / (col("bias_std") + 1e-6))

        # 3. 综合打分
        sdf_final = sdf_zscore.withColumn(
            "total_score",
            round(col("z_momentum") * weight_mom + col("z_bias") * weight_bias, 4)
        )
        return sdf_final

    def simulate_strategy(self, factor_df, top_n=2):
        """根据综合打分选股并生成资金曲线"""
        rank_window = Window.partitionBy("date").orderBy(col("total_score").desc())
        ranked_df = factor_df.withColumn("rank", rank().over(rank_window))

        # 🟢 修复核心：将 code 和 close(价格) 拼接在一起
        portfolio_df = ranked_df.filter(col("rank") <= top_n) \
            .withColumn("code_price", concat_ws(":", col("code"), round(col("close"), 2))) \
            .groupBy("date") \
            .agg(
                round(mean("next_return"), 4).alias("portfolio_return"),
                collect_list("code_price").alias("buy_stocks")  # 收集拼接后的结果
            ) \
            .orderBy("date")

        pdf_returns = portfolio_df.toPandas()
        pdf_returns = pdf_returns.dropna(subset=['portfolio_return'])

        # 收益日期修正为实现日
        pdf_returns['date'] = pd.to_datetime(pdf_returns['date']) + pd.Timedelta(days=1)
        pdf_returns['date'] = pdf_returns['date'].dt.strftime('%Y-%m-%d')
        pdf_returns['equity'] = (1 + pdf_returns['portfolio_return']).cumprod()

        return pdf_returns

    def stop(self):
        if self.spark:
            self.spark.stop()