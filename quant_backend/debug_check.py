import os
import django
import sys
import datetime

# ---------------------------------------------------------
# 1. 初始化 Django 环境 (这样就可以直接运行，不用进 shell)
# ---------------------------------------------------------
# 假设你的项目设置文件是 quant_backend/settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

# ---------------------------------------------------------
# 2. 导入业务逻辑
# ---------------------------------------------------------
from trade.time_utils import get_mock_now
from stocks.models import StockMinuteData

# ---------------------------------------------------------
# 3. 执行无缩进风险的线性检查
# ---------------------------------------------------------
print("\n" + "=" * 10 + " 调试开始 " + "=" * 10)

# 获取上帝时间
mock_now = get_mock_now()
print(f"[1] 系统上帝时间 (Mock Time): \n    {mock_now}")

# 获取数据库最新一条分时数据
# 既然图上有显示，说明肯定有数据，这里直接取
last_data = StockMinuteData.objects.order_by('-date').first()

if last_data:
    db_time = last_data.date
    print(f"[2] 数据库最新数据时间 (DB Last Time): \n    {db_time}")

    # 计算时间差
    diff = mock_now - db_time
    print(f"[3] 两者时间偏差 (Offset): \n    {diff}")

    print("-" * 30)
    if diff.total_seconds() > 0:
        print("结论: 数据库滞后，需要【正向平移】数据")
    elif diff.total_seconds() < 0:
        print("结论: 数据库超前 (未来数据)，需要【负向平移】")
    else:
        print("结论: 时间完全一致，无需平移")
else:
    print("[2] 错误: 数据库里没有任何分时数据！")

print("=" * 10 + " 调试结束 " + "=" * 10 + "\n")