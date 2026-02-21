import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from django.contrib.auth.models import User
from users.models import UserProfile
from trade.models import DailyPerformance, TradeRecord, Order, Position


def check_and_reset():
    print(">>> 🔍 正在诊断用户资产状态...")

    # 假设只有一个活跃用户，或者针对 liuhao24
    user = User.objects.filter(username='liuhao24').first()
    if not user:
        user = User.objects.first()

    if not user:
        print("❌ 未找到用户")
        return

    profile = user.profile
    print(f"\n用户: {user.username}")
    print(f"当前数据库状态:")
    print(f"  - 初始本金 (Initial Capital): {profile.initial_capital}")
    print(f"  - 可用余额 (Balance):         {profile.balance}")
    print(f"  - 总资产 (Total Assets):      {profile.last_total_assets}")
    print(f"  - 总收益 (Total Profit):      {profile.total_profit}")
    print(f"  - 当日收益 (Daily Profit):    {profile.daily_profit}")

    # 检查历史残留
    last_perf = DailyPerformance.objects.filter(user=user).order_by('-date').first()
    if last_perf:
        print(f"  - 最近一条日报: {last_perf.date} | 资产: {last_perf.total_assets}")
    else:
        print(f"  - 日报记录: 无")

    # ================= 强制重置逻辑 =================
    print(f"\n>>> 🛠️ 执行强制重置 (回到 20万 本金)...")

    # 1. 强制设置本金为 20万
    target_capital = Decimal('200000.00')
    profile.initial_capital = target_capital

    # 2. 如果没有交易记录，余额也应该等于本金
    # (您刚才的脚本确认了没有交易记录)
    trade_count = TradeRecord.objects.filter(order__user=user).count()
    if trade_count == 0:
        print(f"  - 检测到无交易记录，重置余额为: {target_capital}")
        profile.balance = target_capital
        profile.withdrawable_cash = target_capital

        # 清空持仓 (双重保险)
        Position.objects.filter(user=user).delete()

    # 3. 重新计算缓存
    profile.update_asset_cache()

    # 4. 清理可能导致图表错误的脏日报数据 (可选: 如果想彻底重置图表)
    # print("  - 清理所有历史日报记录 (重置图表)...")
    # DailyPerformance.objects.filter(user=user).delete()

    print(f"\n✅ 重置后状态:")
    print(f"  - 初始本金: {profile.initial_capital}")
    print(f"  - 总资产:   {profile.last_total_assets}")
    print(f"  - 总收益:   {profile.total_profit} (应为 0.00)")


if __name__ == '__main__':
    check_and_reset()