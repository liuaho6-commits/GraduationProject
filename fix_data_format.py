import os
import sys
import pandas as pd
from tqdm import tqdm
import django

# ================= 1. 极其重要的路径配置 =================
# 当前脚本所在目录 -> E:\GraduationProject
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 后端代码所在目录 -> E:\GraduationProject\quant_backend
BACKEND_DIR = os.path.join(BASE_DIR, "quant_backend")

# 🔴 关键修正：把 'quant_backend' 文件夹加入 Python 搜索路径
# 只有这样，脚本在根目录运行时，才能找到里面的 'stocks' 模块
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, BASE_DIR)

# 设置 Django 配置 (指向 quant_backend/settings.py)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quant_backend.settings")

try:
    django.setup()
    print(f"✅ Django 环境加载成功！(运行目录: {BASE_DIR})")
except Exception as e:
    print(f"❌ Django 加载失败: {e}")
    sys.exit(1)

# 必须在 setup 之后导入
from stocks.models import StockData, StockBasicInfo

# ================= 2. 文件夹名称 (中文括号) =================
# 🔴 保持你正确的文件夹名
DATA_DIR_NAME = "raw_data（沪深3000）"
DATA_DIR = os.path.join(BASE_DIR, DATA_DIR_NAME)

if not os.path.exists(DATA_DIR):
    print(f"❌ 找不到文件夹: {DATA_DIR}")
    sys.exit(1)
else:
    print(f"📂 锁定数据源: {DATA_DIR_NAME}")


# ================= 3. 辅助函数 =================
def get_standard_code(raw_val):
    code = str(raw_val).strip().replace('.csv', '').replace('_daily', '')
    if 'sh.' in code or 'sz.' in code or 'bj.' in code: return code
    if code.startswith('6'):
        return f"sh.{code}"
    elif code.startswith(('0', '3')):
        return f"sz.{code}"
    elif code.startswith(('4', '8')):
        return f"bj.{code}"
    return code


# ================= 4. 执行流程 =================
def run():
    # 1. 清空
    print("\n🧨 [1/3] 清空旧数据...")
    StockData.objects.all().delete()
    StockBasicInfo.objects.all().delete()

    # 2. 导入名称 (忽略行业)
    print("\n📦 [2/3] 导入股票名称...")
    csv_path = os.path.join(DATA_DIR, "stock_basic_info.csv")
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, dtype=str)
        df.rename(columns={'代码': 'code', '名称': 'name', 'code': 'code', 'name': 'name'}, inplace=True)
        objs = []
        for _, row in tqdm(df.iterrows(), total=len(df)):
            c = get_standard_code(row['code'])
            n = str(row['name'])
            if c and n and n != 'nan':
                objs.append(StockBasicInfo(code=c, name=n))  # 无行业字段
        StockBasicInfo.objects.bulk_create(objs)

    # 3. 导入日线
    print("\n📈 [3/3] 导入日线数据...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".csv") and "stock_basic_info" not in f]

    batch = []
    for f in tqdm(files):
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, f))
            if df.empty: continue

            # 列名映射
            df.rename(columns={'日期': 'date', '开盘': 'open', '最高': 'high', '最低': 'low',
                               '收盘': 'close', '成交量': 'volume', '成交额': 'amount'}, inplace=True)

            default_code = get_standard_code(f)

            for _, row in df.iterrows():
                # 处理 amount 空值
                amt = float(row['amount']) if 'amount' in row and pd.notna(row['amount']) else 0.0

                batch.append(StockData(
                    code=get_standard_code(row.get('code', default_code)),
                    date=row['date'],
                    open=row['open'], high=row['high'], low=row['low'], close=row['close'],
                    volume=row['volume'], amount=amt
                ))

                if len(batch) >= 5000:
                    StockData.objects.bulk_create(batch, ignore_conflicts=True)
                    batch = []
        except:
            continue

    if batch: StockData.objects.bulk_create(batch, ignore_conflicts=True)
    print("\n🎉 大功告成！")


if __name__ == "__main__":
    run()