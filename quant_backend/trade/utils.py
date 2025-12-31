from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from users.models import UserProfile
from trade.models import Position, IntradayPerformance, DailyPerformance, TradeRecord
from stocks.models import StockData, StockMinuteData
from .time_utils import get_mock_now
import datetime


def get_price_at_time(code, query_time):
    """获取某时刻的股价 (优先分钟线，降级日线)"""
    # 查 <= query_time 的最近一根分钟线
    row = StockMinuteData.objects.filter(code=code, date__lte=query_time).order_by('-date').first()
    if row: return float(row.close)

    # 降级：查 <= 当天的日线
    row_d = StockData.objects.filter(code=code, date__lte=query_time.date()).order_by('-date').first()
    return float(row_d.close) if row_d else 0.0


# 🟢 核心函数：回放交易记录，计算指定时间点的【持仓市值】和【持仓成本(本金)】
def calculate_holdings_at_time(user, target_time):
    """
    返回: (market_value, total_cost_basis)
    """
    # 1. 获取目标时间点之前的所有成交记录
    # 注意：TradeRecord 没有直接的 user 字段，需通过 order__user 关联查询
    trades = TradeRecord.objects.filter(
        order__user=user,
        trade_time__lte=target_time
    ).select_related('order').order_by('trade_time')

    # 2. 回放交易，重建当时的持仓状态
    holdings = {}  # 格式: {'code': {'vol': 0, 'cost': 0.0}}

    for trade in trades:
        code = trade.stock_code
        direction = trade.order.direction  # 'buy' or 'sell'
        volume = trade.volume
        amount = trade.amount  # 成交金额 (price * vol)
        fee = trade.fee  # 手续费

        if code not in holdings:
            holdings[code] = {'vol': 0, 'cost': 0.0}

        if direction == 'buy':
            # 买入：增加持仓，增加成本 (含手续费)
            holdings[code]['vol'] += volume
            holdings[code]['cost'] += (amount + fee)

        elif direction == 'sell':
            # 卖出：减少持仓，按比例减少成本 (加权平均法)
            current_vol = holdings[code]['vol']
            current_cost = holdings[code]['cost']

            if current_vol > 0:
                # 计算每一股的平均成本
                avg_cost = current_cost / current_vol

                # 卖出部分的成本
                sold_cost = avg_cost * volume

                holdings[code]['vol'] -= volume
                holdings[code]['cost'] -= sold_cost

                # 防止精度误差导致负数
                if holdings[code]['vol'] <= 0:
                    holdings[code]['vol'] = 0
                    holdings[code]['cost'] = 0.0

    # 3. 计算当时的市值
    total_market_value = 0.0
    total_cost_basis = 0.0  # 这就是“本金”

    for code, data in holdings.items():
        vol = data['vol']
        if vol > 0:
            price = get_price_at_time(code, target_time)
            # 市值 = 现价 * 持仓量
            total_market_value += price * vol
            # 本金 = 累计投入成本
            total_cost_basis += data['cost']

    return total_market_value, total_cost_basis


def calculate_user_assets(user):
    """
    计算用户当前总资产（仅计算不记录数据库）
    """
    return record_current_assets_snapshot(user, save_db=False)


def record_current_assets_snapshot(user, current_time=None, save_db=True):
    """
    计算并记录用户资产快照
    """
    if not current_time:
        current_time = get_mock_now()

    try:
        profile = UserProfile.objects.get(user=user)
        balance = float(profile.balance)
    except UserProfile.DoesNotExist:
        balance = 0.0

    # 这里使用最新的 Position 表算市值（比回放更快，适用于“当前”时刻）
    positions = Position.objects.filter(user=user)
    market_value = 0.0

    # 注意：如果要算实时的收益率，也应该用上面的 calculate_holdings_at_time 算成本
    # 但为了性能，快照通常只记总资产。详细收益率交给 View 层计算。

    for pos in positions:
        price = get_price_at_time(pos.stock_code, current_time)
        market_value += price * pos.volume

    total_assets = balance + market_value

    if save_db:
        IntradayPerformance.objects.create(
            user=user,
            time=current_time,
            total_assets=total_assets,
            total_return_rate=0.0  # 暂时填0，由前端或读取时计算
        )
        DailyPerformance.objects.update_or_create(
            user=user,
            date=current_time.date(),
            defaults={
                'total_assets': total_assets,
                'day_profit': 0,
                'day_return_rate': 0,
                'total_return_rate': 0
            }
        )

    return total_assets