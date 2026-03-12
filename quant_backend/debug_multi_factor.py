import os
import sys
import django

# 设置 Django 环境和 Spark 环境变量 (解决 Windows 通信问题)
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
os.environ['SPARK_LOCAL_IP'] = '127.0.0.1'

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

import pandas as pd

if not hasattr(pd.DataFrame, 'iteritems'):
    pd.DataFrame.iteritems = pd.DataFrame.items

from stocks.models import StockData
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lag, round, mean, stddev, avg
from pyspark.sql.window import Window


def test_multi_factor():
    print("=" * 60)
    print("开始验证 Spark 多因子计算与截面打分逻辑 (Evidence-First)")
    print("=" * 60)

    spark = SparkSession.builder \
        .appName("Debug_MultiFactor") \
        .master("local[*]") \
        .config("spark.driver.host", "127.0.0.1") \
        .config("spark.driver.bindAddress", "127.0.0.1") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    # 1. 加载数据
    print("[1/4] 从数据库加载数据...")
    qs = StockData.objects.filter(date__gte='2025-01-01', date__lte='2025-12-31').values('date', 'code', 'close')
    pdf = pd.DataFrame.from_records(qs)
    if pdf.empty:
        print("❌ 致命错误：没有读取到数据！")
        return
    pdf['date'] = pd.to_datetime(pdf['date']).dt.strftime('%Y-%m-%d')
    sdf = spark.createDataFrame(pdf)

    # 2. 时序计算：计算多个基础因子
    print("[2/4] 执行时序矩阵计算：生成多因子...")
    # 按股票代码分组，按时间排序的时序窗口
    ts_window = Window.partitionBy("code").orderBy("date")
    # 计算过去5天的时序窗口（用于算均线和波动率）
    ts_window_5d = Window.partitionBy("code").orderBy("date").rowsBetween(-4, 0)

    sdf_factors = sdf.withColumn("pre_close", lag("close", 1).over(ts_window)) \
        .withColumn("daily_return", (col("close") - col("pre_close")) / col("pre_close")) \
        .withColumn("factor_momentum", round(col("daily_return"), 4)) \
        .withColumn("ma_5", avg("close").over(ts_window_5d)) \
        .withColumn("factor_bias", round((col("close") - col("ma_5")) / col("ma_5"), 4)) \
        .withColumn("factor_volatility", round(stddev("daily_return").over(ts_window_5d), 4))

    # 过滤掉因为均线和滞后产生空值的早期数据
    sdf_factors = sdf_factors.filter(col("factor_volatility").isNotNull() & col("factor_momentum").isNotNull())

    # 3. 截面计算：截面标准化 (Z-Score)
    print("[3/4] 执行截面矩阵计算：Z-Score 标准化...")
    # 按日期分组的截面窗口（同一天的所有股票）
    cs_window = Window.partitionBy("date")

    # 计算横截面的均值和标准差
    sdf_zscore = sdf_factors \
        .withColumn("mom_avg", avg("factor_momentum").over(cs_window)) \
        .withColumn("mom_std", stddev("factor_momentum").over(cs_window)) \
        .withColumn("bias_avg", avg("factor_bias").over(cs_window)) \
        .withColumn("bias_std", stddev("factor_bias").over(cs_window)) \
 \
        # 防止标准差为0导致除以0报错，增加一个小容差 1e-6
    sdf_zscore = sdf_zscore \
        .withColumn("z_momentum", round((col("factor_momentum") - col("mom_avg")) / (col("mom_std") + 1e-6), 4)) \
        .withColumn("z_bias", round((col("factor_bias") - col("bias_avg")) / (col("bias_std") + 1e-6), 4))

    # 4. 多因子打分与选股
    print("[4/4] 执行多因子合成打分 (假设: 动量60% + 偏离度反转40%)...")
    # 我们假设 Bias 越小越好（反转因子），所以权重给负的；Momentum 越大越好，给正的
    weight_mom = 0.6
    weight_bias = -0.4

    sdf_final = sdf_zscore.withColumn(
        "total_score",
        round(col("z_momentum") * weight_mom + col("z_bias") * weight_bias, 4)
    )

    print("\n✅ 多因子计算完成！展示最近一天的股票打分情况（按得分降序排，得分高的优先买入）：")
    # 选取最后一天的数据，按得分倒序展示
    latest_date = sdf_final.agg({"date": "max"}).collect()[0][0]
    sdf_final.filter(col("date") == latest_date) \
        .select("date", "code", "factor_momentum", "factor_bias", "z_momentum", "z_bias", "total_score") \
        .orderBy(col("total_score").desc()) \
        .show()

    spark.stop()
    print("=" * 60)


if __name__ == "__main__":
    test_multi_factor()