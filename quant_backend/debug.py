import os
import django

# 初始化 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from trade.models import SystemSettings, Strategy
from stocks.models import StockData


def run_prep():
    print("=" * 50)
    print("【第一步】读取核心调度任务 trade/tasks.py 的源码")
    print("=" * 50)
    try:
        # 读取 tasks.py 看看目前的时钟 tick 是怎么写的
        with open('trade/tasks.py', 'r', encoding='utf-8') as f:
            print(f.read()[:1500])  # 打印前1500个字符足够看清逻辑
    except Exception as e:
        print(f"读取失败: {e}")

    print("\n" + "=" * 50)
    print("【第二步】检查上帝视角：时间系统与真实数据的对齐情况")
    print("=" * 50)
    try:
        settings = SystemSettings.get_settings()
        print(f"1. 当前系统模拟时间 (Mock Time): {settings.current_mock_time}")
        print(f"2. 当前时间流速倍率 (Time Speed): {settings.time_speed}x")

        latest_stock = StockData.objects.order_by('-date').first()
        oldest_stock = StockData.objects.order_by('date').first()
        if latest_stock and oldest_stock:
            print(f"3. 股票日线数据区间: {oldest_stock.date} 至 {latest_stock.date}")
        else:
            print("3. ⚠️ 数据库中尚未发现日线股票数据！")
    except Exception as e:
        print(f"系统设置读取异常: {e}")

    print("\n" + "=" * 50)
    print("【第三步】检查现存的量化策略")
    print("=" * 50)
    try:
        strategies = Strategy.objects.all()
        print(f"当前数据库中共有 {strategies.count()} 个策略")
        for s in strategies:
            print(f" -> ID: {s.id} | 名称: {s.name} | 状态: {s.status} | 用户: {s.user.username}")
            print(f"    股票池: {s.stock_pool}")
            if s.code:
                print(f"    策略代码前缀: {s.code[:50].replace(chr(10), ' ')}...")
    except Exception as e:
        print(f"策略读取异常: {e}")

    print("\n>>> 探测完成，请将以上输出完整发给 AI <<<")


if __name__ == '__main__':
    run_prep()