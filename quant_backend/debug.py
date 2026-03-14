import os
import django
from decimal import Decimal

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from users.models import UserProfile
from trade.models import DailyPerformance
from trade.time_utils import get_mock_now


def run_debug():
    print("============== 🔍 仪表盘数据分裂追踪 ==============")
    profile = UserProfile.objects.first()
    if not profile:
        print("❌ 找不到用户，请先注册/登录并初始化资产！")
        return

    user = profile.user
    now = get_mock_now()

    # 强制刷新一次最新的总资产 (和前端请求 UserInfoView 一样)
    profile.update_asset_cache()

    # 1. 获取当前 UserProfile 里存的、准备发给顶部卡片的数据
    stored_daily_profit = profile.daily_profit

    # 2. 模拟前端底层曲线图表的逻辑，推算今日真实物理收益
    yesterday_perf = DailyPerformance.objects.filter(
        user=user, date__lt=now.date()
    ).order_by('-date').first()

    if yesterday_perf:
        base_assets = yesterday_perf.total_assets
        print(f"✅ 找到上个交易日({yesterday_perf.date})结算资产基准: ￥{base_assets:.2f}")
    else:
        base_assets = profile.initial_capital
        print(f"⚠️ 未找到历史结算记录，使用初始资金基准: ￥{base_assets:.2f}")

    current_assets = profile.last_total_assets
    real_daily_profit = current_assets - base_assets

    print("\n📊 核心数据对峙:")
    print(f"  [现在的总资产]: ￥{current_assets:.2f}")
    print(f"  [对比基准资产]: ￥{base_assets:.2f}")
    print("-" * 40)
    print(f"  ❌ 顶部卡片读取的缓存收益 (UserProfile): ￥{stored_daily_profit:.2f}")
    print(f"  ✅ 曲线图表计算的实时真实收益: ￥{real_daily_profit:.2f}")

    if abs(stored_daily_profit - real_daily_profit) > 0.01:
        print("\n🚨 铁证如山！抓到 Bug 了！数据确实分裂了！")
        print("🕵️‍♂️ 破案分析：")
        print("你的系统是高频跳动的，引擎买卖股票导致 `last_total_assets` 实时变化。")
        print("下方的图表很聪明，它每次都用现在的总资产减去昨天的去算实时收益。")
        print("但最顶部的卡片读的 `daily_profit` 字段是个死木头，它没有实时更新！")
    else:
        print("\n✅ 数据一致，此时并未发生分裂。你可以去前端下几笔单子再运行本脚本测试。")


if __name__ == '__main__':
    run_debug()