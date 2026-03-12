import os
import django
import sys
import datetime
from decimal import Decimal
from collections import defaultdict
import bisect

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quant_backend.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import UserProfile
from trade.models import Order, Position
from stocks.models import StockData, StockMinuteData
from trade.time_utils import get_mock_now
from trade.views import calculate_asset_status


def run_debug():
    User = get_user_model()
    # 默认获取第一个用户，如果你的测试账号不是第一个，请修改这里的查询条件
    user = User.objects.get(username='liuhao24')

    if not user:
        print("未找到用户，请确保数据库中有用户数据。")
        return

    print(f"========== 正在调试用户: {user.username} 的日内收益计算 ==========")

    now = get_mock_now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now)
    print(f"[系统时间] 当前系统时间: {now}")

    profile = UserProfile.objects.get(user=user)
    current_balance = profile.balance
    initial_capital = profile.initial_capital if profile.initial_capital > 0 else Decimal('200000.0')

    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    print(f"[时间锚点] 收益计算起点 (今日09:30): {start}")

    if now < start:
        print("当前时间早于09:30，返回空数据是正常的。")
        return

    # 1. 计算基准资产
    yesterday_close_time = (start - datetime.timedelta(days=1)).replace(hour=15, minute=0, second=0)
    base_assets, _, _, _, _ = calculate_asset_status(user, yesterday_close_time)
    if base_assets <= 0:
        base_assets = initial_capital
    print(f"[基准资产] 昨收基准时间: {yesterday_close_time}")
    print(f"[基准资产] 昨收总资产 (base_assets): {base_assets}")

    # 2. 获取今日订单
    orders_today = Order.objects.filter(
        user=user, status='filled', order_time__gte=start, order_time__lte=now
    ).order_by('order_time')
    print(f"[今日订单] 数量: {len(orders_today)}")

    # 3. 倒推现金与持仓
    cash_change_today = Decimal('0.0')
    for o in orders_today:
        cost = Decimal(str(o.price)) * Decimal(o.volume)
        if o.direction == 'buy':
            cash_change_today -= cost
        else:
            cash_change_today += cost

    start_cash = current_balance - cash_change_today
    print(f"[资金倒推] 当前可用资金: {current_balance}, 今日变动: {cash_change_today}, 倒推得出09:30资金: {start_cash}")

    current_positions_qs = Position.objects.filter(user=user, volume__gt=0)
    current_holdings = {p.stock_code: p.volume for p in current_positions_qs}
    print(f"[当前持仓] 数据库最新持仓: {current_holdings}")

    start_holdings = current_holdings.copy()
    for o in reversed(orders_today):
        if o.direction == 'buy':
            start_holdings[o.stock_code] = start_holdings.get(o.stock_code, 0) - o.volume
        else:
            start_holdings[o.stock_code] = start_holdings.get(o.stock_code, 0) + o.volume

    start_holdings = {k: v for k, v in start_holdings.items() if v > 0}
    print(f"[持仓倒推] 09:30 起始持仓: {start_holdings}")

    active_stocks = set(start_holdings.keys())
    for o in orders_today:
        active_stocks.add(o.stock_code)
    print(f"[活跃股票] 今天需要查分钟线的股票: {active_stocks}")

    if not active_stocks:
        print("!!! 警告: 没有活跃持仓，也没有今日订单，总资产全为现金，收益率必定是一条直线(0%) !!!")

    last_prices = {}
    price_cache = defaultdict(list)

    if active_stocks:
        for code in active_stocks:
            last_daily = StockData.objects.filter(code=code, date__lt=start.date()).order_by('-date').first()
            last_prices[code] = Decimal(str(last_daily.close)) if last_daily else Decimal('0.0')
        print(f"[昨收兜底价] {last_prices}")

        minutes = StockMinuteData.objects.filter(
            code__in=active_stocks, date__gte=start, date__lte=now
        ).order_by('date').values('code', 'date', 'close')

        for m in minutes:
            dt = m['date']
            if timezone.is_naive(dt): dt = timezone.make_aware(dt)
            price_cache[m['code']].append((dt, Decimal(str(m['close']))))

        for code in active_stocks:
            print(f"[分钟线数据] 股票 {code} 在库里查到了 {len(price_cache[code])} 条今日的分钟线数据")
            if len(price_cache[code]) == 0:
                print(
                    f"!!! 致命问题: 股票 {code} 没有今天（{start.date()}）的分钟级数据，市值将一直使用昨收价，导致图表是一条直线 !!!")

    # 4. 模拟时间遍历
    print("\n========== 开始模拟遍历 09:30 到 当前时间 ==========")
    curr = start
    curr_cash = start_cash
    curr_holdings = defaultdict(int, start_holdings)
    order_idx = 0
    num_orders = len(orders_today)

    while curr <= now:
        while order_idx < num_orders:
            o = orders_today[order_idx]
            o_time = o.order_time if timezone.is_aware(o.order_time) else timezone.make_aware(o.order_time)
            if o_time > curr: break

            cost = Decimal(str(o.price)) * Decimal(o.volume)
            if o.direction == 'buy':
                curr_cash -= cost
                curr_holdings[o.stock_code] += o.volume
            else:
                curr_cash += cost
                curr_holdings[o.stock_code] -= o.volume
            order_idx += 1

        mv = Decimal('0.0')
        debug_prices = {}
        for code, vol in curr_holdings.items():
            if vol <= 0: continue
            price = last_prices.get(code, Decimal(0))
            data_list = price_cache.get(code)
            if data_list:
                idx = bisect.bisect_right(data_list, (curr, Decimal('99999999')))
                if idx > 0:
                    price = data_list[idx - 1][1]
                    last_prices[code] = price
            mv += Decimal(vol) * price
            debug_prices[code] = price

        curr_assets = curr_cash + mv
        profit = curr_assets - base_assets
        rate = (profit / base_assets * 100) if base_assets > 0 else 0

        print(
            f"[{curr.strftime('%H:%M')}] 现金:{curr_cash:.2f} | 市值:{mv:.2f} (股价:{debug_prices}) | 总资产:{curr_assets:.2f} | 收益率:{rate:.2f}%")

        curr += datetime.timedelta(minutes=5)
        if curr.hour == 11 and curr.minute > 30:
            curr = curr.replace(hour=13, minute=0)

    print("========== 调试结束 ==========")


if __name__ == '__main__':
    run_debug()