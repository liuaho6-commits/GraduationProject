import os
from pyspark.sql import SparkSession

# 获取当前脚本所在路径
current_path = os.path.dirname(os.path.abspath(__file__))
jar_path = os.path.join(current_path, "mysql-connector-java-8.0.28.jar")

# 1. 创建 Spark 会话
spark = SparkSession.builder \
    .appName("StockDataToMySQL") \
    .config("spark.jars", jar_path) \
    .config("spark.driver.extraClassPath", jar_path) \
    .getOrCreate()

print("Spark 会话已启动，正在读取 CSV 数据...")

# 2. 读取数据
df = spark.read.csv("raw_data/*.csv", header=True, inferSchema=True)

# 3. 挑选列并清洗脏数据
# .na.drop() 会自动删掉任何包含空值的行，确保入库数据质量
final_df = df.select("code", "date", "open", "high", "low", "close", "volume", "amount").na.drop()

print(f"数据清洗完成，准备写入 MySQL。有效行数: {final_df.count()}")

# 4. 写入数据库
final_df.write \
    .format("jdbc") \
    .option("url", "jdbc:mysql://127.0.0.1:3306/quant_db?useSSL=false&allowPublicKeyRetrieval=true") \
    .option("dbtable", "stock_data") \
    .option("user", "root") \
    .option("password", "liuhao") \
    .option("driver", "com.mysql.cj.jdbc.Driver") \
    .mode("append") \
    .save()

print("✅ 所有数据已成功导入 MySQL！")
spark.stop()