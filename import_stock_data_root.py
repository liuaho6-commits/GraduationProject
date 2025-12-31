import os
import sys
import django
import pandas as pd
from pathlib import Path
import time

# ================= 1. 环境配置 (关键) =================
# 获取当前脚本所在目录 (E:\GraduationProject)
BASE_DIR = Path(__file__).resolve().parent

# 将后端项目目录加入 Python 搜索路径，否则找不到 quant_backend
sys.path.append(str(BASE_DIR / "quant_backend"))

# 设置 Django 配置文件路径
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quant_backend.settings")
django.setup()

# 导入模型 (必须在 setup() 之后)
from stocks.models import StockData

# ================= 2. 数据路径配置 =================
# 根据你的截图，数据在根目录下的 "raw_data（沪深3000）" 文件夹
DATA_DIR = BASE_DIR / "raw_data（沪深3000）"


def import_data():
    if not DATA_DIR.exists():
        print(f"❌ 错误：找不到数据文件夹: {DATA_DIR}")
        print("请检查文件夹名称是否完全一致（注意中文括号）")
        return

    # 获取所有 csv 文件
    csv_files = list(DATA_DIR.glob("*.csv"))
    total_files = len(csv_files)
    print(f"📂 找到 {total_files} 个CSV文件，准备开始导入...")

    # 用于批量插入的缓存列表
    batch_list = []
    BATCH_SIZE = 3000  # 每 3000 条写入一次，避免内存溢出
    total_inserted = 0
    start_time = time.time()

    for index, file_path in enumerate(csv_files):
        file_name = file_path.name

        # 1. 跳过股票名称表 (因为你说了这部分已经在数据库里了)
        if "stock_basic_info" in file_name:
            continue

        # 2. 提取股票代码 (sh.600000.csv -> sh.600000)
        stock_code = file_name.replace(".csv", "")

        # 打印进度 (每处理100个文件显示一次)
        if index % 100 == 0:
            print(f"🚀 进度 [{index}/{total_files}] 正在处理: {stock_code}")

        try:
            # 3. 读取 CSV
            # 常见编码是 utf-8-sig 或 gbk，先试 utf-8-sig
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')

            # 4. 列名标准化 (兼容中文和英文列名)
            rename_map = {
                '日期': 'date', 'date': 'date',
                '开盘': 'open', 'open': 'open',
                '最高': 'high', 'high': 'high',
                '最低': 'low', 'low': 'low',
                '收盘': 'close', 'close': 'close',
                '成交量': 'volume', 'volume': 'volume',
                '成交额': 'amount', 'amount': 'amount'
            }
            df.rename(columns=rename_map, inplace=True)

            # 确保日期列是标准格式
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])

            # 5. 构建模型对象列表
            for _, row in df.iterrows():
                # 跳过非法数据
                if pd.isna(row['date']):
                    continue

                stock_data = StockData(
                    code=stock_code,
                    date=row['date'],
                    open=row['open'] if not pd.isna(row['open']) else 0,
                    high=row['high'] if not pd.isna(row['high']) else 0,
                    low=row['low'] if not pd.isna(row['low']) else 0,
                    close=row['close'] if not pd.isna(row['close']) else 0,
                    volume=row['volume'] if not pd.isna(row['volume']) else 0,
                    amount=row['amount'] if not pd.isna(row['amount']) else 0
                )
                batch_list.append(stock_data)

            # 6. 批量写入数据库
            if len(batch_list) >= BATCH_SIZE:
                StockData.objects.bulk_create(batch_list)
                total_inserted += len(batch_list)
                print(f"   ---> 已存入 {total_inserted} 条数据...")
                batch_list = []  # 清空缓存

        except Exception as e:
            print(f"⚠️ 处理文件 {file_name} 时出错: {e}")
            continue

    # 7. 处理剩余的尾巴
    if batch_list:
        StockData.objects.bulk_create(batch_list)
        total_inserted += len(batch_list)

    end_time = time.time()
    duration = end_time - start_time
    print(f"\n✅ 全部完成！")
    print(f"📊 共导入数据: {total_inserted} 条")
    print(f"⏱️ 总耗时: {duration:.2f} 秒")


if __name__ == "__main__":
    # 如果你想每次运行前先清空旧数据，取消下面这行的注释
    # StockData.objects.all().delete()

    import_data()