import os
import sys
import django
from datetime import datetime, time

# 1. 初始化 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from stocks.models import StockMinuteData


def analyze_future_data():
    print("--- 🔍 DEBUG: 分析分钟线数据 (Future/Floating Volume) ---")

    # 获取当前系统时间
    now = datetime.now()
    current_time = now.time()
    current_date = now.date()

    print(f"SERVER TIME: {now}")

    # 尝试获取今日有数据的任意一只股票
    # 注意：如果你是在非交易时间调试，或者使用了模拟时间，请确保这里逻辑匹配
    target_symbol = '000001'  # 默认检查平安银行，你可以修改为图表中出错的股票代码

    print(f"\n检查股票: {target_symbol} 日期: {current_date}")

    records = StockMinuteData.objects.filter(
        symbol=target_symbol,
        date=current_date
    ).order_by('time')

    total_count = records.count()
    print(f"今日总记录数: {total_count}")

    if total_count == 0:
        print("⚠️ 今日无数据。请确认是否已运行 init_minute_data 或爬虫。")
        # 尝试查找最近一天的数据进行结构分析
        last_record = StockMinuteData.objects.filter(symbol=target_symbol).last()
        if last_record:
            print(f"  -> 切换至检查最近一次历史数据: {last_record.date}")
            records = StockMinuteData.objects.filter(symbol=target_symbol, date=last_record.date).order_by('time')
            current_time = time(9, 40)  # 假定一个盘中时间来模拟检查
            print(f"  -> 模拟盘中时间为: {current_time} (用于检测逻辑)")
        else:
            return

    # 1. 检查是否存在“未来数据”
    # 逻辑：当前时间之后的记录是否被创建了？
    future_records = [r for r in records if r.time > current_time]
    future_count = len(future_records)

    print(f"\n1. 未来数据检查 (Time > {current_time}):")
    print(f"   数量: {future_count} 条")

    if future_count > 0:
        first_fut = future_records[0]
        last_fut = future_records[-1]
        print(f"   第一条未来数据: Time={first_fut.time}, Price={first_fut.price}, Vol={first_fut.volume}")
        print(f"   最后一条未来数据: Time={last_fut.time}, Price={last_fut.price}, Vol={last_fut.volume}")

        if first_fut.volume == 0:
            print("   -> 🔴 发现问题根源: 数据库预填充了未来的时间点，且 Volume=0。")
            print("      前端 ECharts 如果没有忽略 0 值，或者 Y 轴 min 没设为 0，就会出现'悬空'或'多余'的线。")
        else:
            print("   -> 🔴 严重警告: 未来时间点竟然有非零成交量！数据源可能存在错位。")
    else:
        print("   ✅ 未发现未来数据 (后端过滤正常 或 尚未初始化未来数据)。")

    # 2. 检查 Volume 数据特征 (解决'悬空'疑惑)
    print(f"\n2. 成交量数据特征:")
    volumes = [r.volume for r in records]
    null_vols = records.filter(volume__isnull=True).count()
    zero_vols = records.filter(volume=0).count()

    print(f"   None 值数量: {null_vols}")
    print(f"   0 值数量: {zero_vols}")
    if volumes:
        print(f"   最大量: {max(volumes)}")
        # 检查是否有负数（导致悬空的一种可能）
        min_vol = min(volumes)
        print(f"   最小量: {min_vol}")
        if min_vol < 0:
            print("   -> 🔴 发现负成交量！这会导致图表绘制异常。")


if __name__ == "__main__":
    analyze_future_data()