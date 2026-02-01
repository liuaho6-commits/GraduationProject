import os
import sys
import django
import pandas as pd
from datetime import datetime, timedelta

# 1. Setup Django Environment
# 自动适配路径，无需手动修改
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from stocks.models import StockMinuteData


def debug_5min_aggregation():
    # ------------------------------------------------------------------
    TARGET_CODE = '600000.SH'  # 这里对应你数据库里的 code 字段
    # ------------------------------------------------------------------

    print(f"--- 正在调试 5分钟K线数据问题: {TARGET_CODE} ---")

    # 1. 检查数据库原始数据 (Raw Data Check)
    print("\n[Step 1] 检查数据库中最新的原始分钟数据 (Last 15 records):")
    try:
        # 修正点：使用 code 过滤，使用 date 排序
        qs = StockMinuteData.objects.filter(code=TARGET_CODE).order_by('-date')[:15]

        data_list = []
        if not qs.exists():
            print(f"ERROR: 找不到 {TARGET_CODE} 的分钟数据！")
            return

        print(f"{'Time (Raw DB)':<25} | {'Price':<10} | {'Volume':<15}")
        print("-" * 60)

        for item in reversed(qs):  # 按时间正序打印
            # 修正点：字段名改为 date 和 close
            print(f"{str(item.date):<25} | {item.close:<10} | {item.volume:<15}")
            data_list.append({
                'time': item.date,
                'price': float(item.close),
                'volume': item.volume
            })

    except Exception as e:
        print(f"读取数据库失败: {e}")
        return

    # 2. 模拟 Pandas Resample 聚合 (Simulation)
    print("\n[Step 2] 模拟 Pandas 5分钟聚合 (检查时间偏移):")

    if not data_list:
        return

    df = pd.DataFrame(data_list)
    df['time'] = pd.to_datetime(df['time'])
    # 必须去掉时区信息以便和 Resample 默认行为对比，或者保持一致。这里先保留原样。
    df.set_index('time', inplace=True)

    try:
        rule = '5Min'

        # 方式 1: Label='left', Closed='left' (常见默认值: 10:00 包含 10:00-10:04)
        # 结果显示的 '10:00' 代表这段时间的开始
        res_left = df['volume'].resample(rule, label='left', closed='left').sum()

        # 方式 2: Label='right', Closed='right' (A股常用: 10:05 包含 10:01-10:05)
        # 结果显示的 '10:05' 代表这段时间的结束
        res_right = df['volume'].resample(rule, label='right', closed='right').sum()

        print("\n--- 模拟结果对比 ---")
        print(f"{'Resampled Time':<25} | {'Vol (Label=Left)':<18} | {'Vol (Label=Right)':<18}")

        all_indices = sorted(list(set(res_left.index) | set(res_right.index)))

        for idx in all_indices:
            vol_left = res_left.get(idx, 0)
            vol_right = res_right.get(idx, 0)

            t_str = idx.strftime('%Y-%m-%d %H:%M:%S')
            print(f"{t_str:<25} | {vol_left:<18} | {vol_right:<18}")

        print("\n[分析指南]")
        print("1. 请看 'Time (Raw DB)' 最后一行：如果它是未来的时间，那就是数据源错了。")
        print("2. 如果 Raw DB 正常，请看下面聚合对比。")
        print("   - 如果前端图表显示的时间点，对应的是 'Vol (Label=Left)' 的数值，但你希望它代表结束时间，那就是错位了。")

    except Exception as e:
        print(f"Pandas 模拟失败: {e}")


if __name__ == "__main__":
    debug_5min_aggregation()