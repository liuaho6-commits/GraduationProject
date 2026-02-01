import os
import django
import sys

# 初始化 Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from stocks.models import StockMinuteData

target_code = 'sh.688256'  # 你的问题股票

print(f"\n🔍 正在检查股票 {target_code} 的数据完整性...")

# 1. 查总条数
count = StockMinuteData.objects.filter(code=target_code).count()
print(f"数据总条数: {count}")

if count > 0:
    # 2. 查最新的一条数据
    latest = StockMinuteData.objects.filter(code=target_code).order_by('-date').first()
    print(f"最新数据时间: {latest.date}")

    # 3. 查2024年以后的数据有没有
    count_2024 = StockMinuteData.objects.filter(code=target_code, date__year__gte=2024).count()
    print(f"2024年及以后数据条数: {count_2024}")

    if count_2024 == 0:
        print("\n❌ 结论: 数据库里确实【没有】该股票2024年的数据！")
        print("💡 建议: 请重新运行数据下载脚本 (python manage.py init_minute_data 或 download_real_3y)")
    else:
        print("\n✅ 结论: 数据库里【有】2024年的数据。")
else:
    print("❌ 错误: 该股票没有任何数据！")

print("\n")