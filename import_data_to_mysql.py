import os
import sys
import django
import pandas as pd
from tqdm import tqdm

# ================= 1. 核心路径配置 (关键修正) =================
# 获取当前脚本所在的绝对路径 (即 E:\GraduationProject)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取后端项目路径 (即 E:\GraduationProject\quant_backend)
PROJECT_PATH = os.path.join(BASE_DIR, "quant_backend")

# 关键步骤：将两个路径都加入 Python 搜索列表
# 这样 Python 既能找到 'quant_backend' 包，也能直接找到内部的 'stocks' 包
sys.path.insert(0, PROJECT_PATH)
sys.path.insert(0, BASE_DIR)

# ================= 2. 初始化 Django 环境 =================
# 这里加一个自动判断逻辑
# 如果 settings.py 直接在 quant_backend 目录下（扁平结构），模块名通常是 'settings'
# 如果是标准结构（quant_backend/quant_backend/settings.py），模块名是 'quant_backend.settings'

# 先尝试标准配置
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quant_backend.settings")

try:
    django.setup()
    print(f"✅ Django 环境加载成功！(配置: quant_backend.settings)")
except Exception as e_standard:
    # 如果失败，说明可能是扁平结构，尝试直接用 'settings'
    print(f"⚠️ 标准加载失败，尝试扁平化加载... ({e_standard})")
    try:
        os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
        django.setup()
        print(f"✅ Django 环境加载成功！(配置: settings)")
    except Exception as e_flat:
        print(f"❌ Django 环境加载彻底失败。请检查 settings.py 是否存在。")
        print(f"错误详情 1: {e_standard}")
        print(f"错误详情 2: {e_flat}")
        sys.exit(1)

# ================= 3. 导入模型 =================
# 必须在 django.setup() 之后导入
# 由于我们将 PROJECT_PATH 加入了 sys.path，可以直接 import stocks
try:
    from stocks.models import StockData, StockBasicInfo
except ImportError:
    # 备用方案：带上项目前缀
    from quant_backend.stocks.models import StockData, StockBasicInfo

# 数据源文件夹路径
DATA_DIR = os.path.join(BASE_DIR, "raw_data")


# ================= 4. 数据导入逻辑 (保持不变) =================

def import_stock_names():
    file_path = os.path.join(DATA_DIR, "stock_basic_info.csv")
    if not os.path.exists(file_path):
        print(f"⚠️ 跳过名称导入：未找到 {file_path}")
        return

    print(f"📂 正在读取股票列表: {file_path}")
    try:
        df = pd.read_csv(file_path)
        # 兼容 Baostock 和 AkShare 的列名
        df.rename(columns={'代码': 'code', '名称': 'name', 'code_name': 'name'}, inplace=True)

        stock_list = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="导入基本信息"):
            code = str(row['code'])
            name = str(row['name'])
            stock_list.append(StockBasicInfo(code=code, name=name))

        StockBasicInfo.objects.bulk_create(stock_list, ignore_conflicts=True)
        print(f"✅ 股票名称导入完成！共 {len(stock_list)} 条。")
    except Exception as e:
        print(f"❌ 导入股票名称失败: {e}")


def import_daily_data():
    files = [f for f in os.listdir(DATA_DIR)
             if f.endswith(".csv") and "basic_info" not in f and "5min" not in f]

    print(f"\n📂 发现 {len(files)} 个日线数据文件，准备导入...")

    batch_size = 5000
    pending_objects = []

    for file_name in tqdm(files, desc="处理文件进度"):
        file_path = os.path.join(DATA_DIR, file_name)
        try:
            df = pd.read_csv(file_path)
            if df.empty: continue

            # 列名映射
            column_mapping = {
                '日期': 'date', '代码': 'code',
                '开盘': 'open', '最高': 'high', '最低': 'low', '收盘': 'close',
                '成交量': 'volume', '成交额': 'amount'
            }
            df.rename(columns=column_mapping, inplace=True)

            for _, row in df.iterrows():
                # 处理股票代码
                stock_code = str(row.get('code', file_name.replace('.csv', '').replace('sh.', '').replace('sz.', '')))
                if 'sh.' in file_name or 'sz.' in file_name:
                    if not stock_code.startswith(('sh.', 'sz.')):
                        prefix = file_name.split('.')[0] + '.'
                        stock_code = prefix + stock_code

                stock_data = StockData(
                    code=stock_code,
                    date=row['date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['volume']),
                    amount=float(row['amount']) if 'amount' in row else 0.0
                )
                pending_objects.append(stock_data)

                if len(pending_objects) >= batch_size:
                    StockData.objects.bulk_create(pending_objects, ignore_conflicts=True)
                    pending_objects = []

        except Exception as e:
            continue

    if pending_objects:
        StockData.objects.bulk_create(pending_objects, ignore_conflicts=True)
    print(f"✅ 所有日线数据导入数据库完成！")


if __name__ == "__main__":
    print(f"🚀 开始运行数据导入脚本...")
    import_stock_names()
    import_daily_data()
    print("\n🎉🎉🎉 全部任务执行完毕！")