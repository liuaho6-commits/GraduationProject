import os
import sys
import django

# =====================================================================
# 【新增环境修补】：解决 Windows 下 Python worker failed to connect back 问题
# =====================================================================
# 1. 强制指定 PySpark 的 Driver 和 Worker 都使用当前的 Anaconda 环境 Python
os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
# 2. 强制绑定本地 IPv4，防止 Windows 主机名解析到 IPv6 导致 Socket 连不上
os.environ['SPARK_LOCAL_IP'] = '127.0.0.1'
# =====================================================================

# 设置 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

import pandas as pd

# 【修复补丁】：兼容 Pandas 2.0+ 与老版本 PySpark 的冲突
if not hasattr(pd.DataFrame, 'iteritems'):
    pd.DataFrame.iteritems = pd.DataFrame.items

from stocks.models import StockData

# 导入 PySpark 相关库
try:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, lag, round
    from pyspark.sql.window import Window
except ImportError:
    print("❌ 致命错误: 未安装 pyspark。请运行: pip install pyspark")
    sys.exit(1)


def test_spark_matrix():
    print("=" * 60)
    print("开始验证 Spark 分布式环境与矩阵转换 (Evidence-First)")
    print("=" * 60)

    # 1. 启动 Spark Session
    print("[1/4] 正在初始化 Spark Session...")
    try:
        # local[*] 表示使用本地所有可用的 CPU 核心进行计算模拟
        # 新增 config 强化本地 IP 绑定
        spark = SparkSession.builder \
            .appName("QuantBacktest_FactorMatrix") \
            .master("local[*]") \
            .config("spark.driver.host", "127.0.0.1") \
            .config("spark.driver.bindAddress", "127.0.0.1") \
            .getOrCreate()
        # 降低 Spark 日志级别，防止控制台被刷屏
        spark.sparkContext.setLogLevel("ERROR")
        print("  -> Spark Session 初始化成功！(出现的 winutils 警告可忽略)")
    except Exception as e:
        print(f"❌ 致命错误: Spark 初始化失败。请检查是否正确安装了 Java 环境。\n错误信息: {e}")
        return

    # 2. 从数据库加载数据
    print("\n[2/4] 正在从 Django ORM 加载数据...")
    # 只提取我们计算需要的核心字段，减少内存开销
    qs = StockData.objects.all().values('date', 'code', 'close')
    pdf = pd.DataFrame.from_records(qs)

    if pdf.empty:
        print("❌ 致命错误: 未读取到任何数据。")
        return

    # 将日期格式化为字符串，避免 Spark 解析某些 datetime 对象时报错
    pdf['date'] = pd.to_datetime(pdf['date']).dt.strftime('%Y-%m-%d')
    print(f"  -> 成功拉取并转换为 Pandas DataFrame，共 {len(pdf)} 行。")

    # 3. 转换为 Spark DataFrame
    print("\n[3/4] 正在构建 Spark DataFrame...")
    sdf = spark.createDataFrame(pdf)
    print("  -> 成功创建 Spark DataFrame！")

    # 4. 计算简单动量因子 (昨日收益率) 并构建截面矩阵
    print("\n[4/4] 正在执行分布式矩阵操作 (计算收益率并 Pivot)...")

    # 定义窗口函数：按股票代码(code)分组，按日期(date)排序
    windowSpec = Window.partitionBy("code").orderBy("date")

    # 分布式计算 1 日收益率: (close - pre_close) / pre_close
    sdf_with_return = sdf.withColumn("pre_close", lag("close", 1).over(windowSpec)) \
        .withColumn("daily_return", round((col("close") - col("pre_close")) / col("pre_close"), 4))

    # 【核心：矩阵优化】 Pivot 操作：将行转列，构建真正的因子截面矩阵
    matrix_df = sdf_with_return.filter(col("daily_return").isNotNull()) \
        .groupBy("date") \
        .pivot("code") \
        .avg("daily_return") \
        .orderBy(col("date").desc())

    print("\n✅ 构建的因子截面矩阵 (展示最近 5 个交易日，列为这 5 只股票的收益率)：")
    matrix_df.show(5)

    print("=" * 60)
    print("如果你能看到上面的矩阵表格，说明 Python -> Spark -> 分布式计算全链路已打通！")
    print("=" * 60)

    spark.stop()


if __name__ == "__main__":
    test_spark_matrix()