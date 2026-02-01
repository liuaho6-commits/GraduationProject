import os
import django
import datetime

# 初始化 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from stocks.models import StockMinuteData, StockBasicInfo
from trade.time_utils import get_mock_now


def analyze_gap():
    mock_now = get_mock_now()
    print(f"\n======== 🕵️ 数据断层深度诊断 ========")
    print(f"当前系统上帝时间 (Mock Time): {mock_now}")

    # 选取几只典型股票进行检测
    target_codes = ['sh.688256', 'sz.300308', 'sz.300476']

    for code in target_codes:
        print(f"\n>>> 正在分析股票: {code}")

        # 1. 查上帝时间之前的最新一条 (Past)
        past_obj = StockMinuteData.objects.filter(
            code=code,
            date__lte=mock_now
        ).order_by('-date').first()

        # 2. 查上帝时间之后的最近一条 (Future)
        future_obj = StockMinuteData.objects.filter(
            code=code,
            date__gt=mock_now
        ).order_by('date').first()

        # --- 分析结果 ---
        if past_obj:
            print(f"   [Past]   最近的历史数据: {past_obj.date} (距离现在 {(mock_now - past_obj.date).days} 天)")
        else:
            print(f"   [Past]   ❌ 上帝时间之前没有任何数据！")

        if future_obj:
            print(f"   [Future] 最近的未来数据: {future_obj.date} (距离现在 {(future_obj.date - mock_now).days} 天)")
        else:
            print(f"   [Future] ❌ 上帝时间之后没有任何数据！")

        # 结论判断
        if past_obj and future_obj:
            gap_days = (future_obj.date - past_obj.date).days
            if gap_days > 5:
                print(f"   ⚠️  检测到严重断层! 缺失了约 {gap_days} 天的数据。")
                print(f"       这就是为什么你看到的是旧数据，因为上帝时间掉进了这个【真空期】。")
            else:
                print(f"   ✅ 数据连续性良好，但仍显示旧数据？可能存在时区微小差异。")
        elif not past_obj and future_obj:
            print(f"   ⚠️  所有数据都在上帝时间之后。请检查 mock_time.json 是否设置得太早。")

    print("\n======================================")


if __name__ == '__main__':
    analyze_gap()