import datetime
import logging
from decimal import Decimal
from django.db import transaction
from .time_utils import get_mock_now

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    交易撮合与策略执行引擎
    """

    def __init__(self):
        # 记录策略执行状态，防止同一窗口被系统秒级时钟多次触发
        self.run_records = {'open': {}, 'close': {}}

    def run_all_active_strategies(self):
        """
        执行所有处于 'active' 状态的策略
        """
        from .models import Strategy

        try:
            now = get_mock_now()
            date_str = now.strftime('%Y-%m-%d')
            time_type = None

            # 开盘时段：09:30 - 09:35
            if now.hour == 9 and 30 <= now.minute <= 35:
                time_type = 'open'
            # 尾盘时段：14:50 - 14:59
            elif now.hour == 14 and 50 <= now.minute <= 59:
                time_type = 'close'

            if not time_type:
                return

            if date_str not in self.run_records[time_type]:
                self.run_records[time_type][date_str] = []

            active_strategies = Strategy.objects.filter(status='active').select_related('user')

            for strategy in active_strategies:
                if strategy.id in self.run_records[time_type][date_str]:
                    continue

                self.execute_strategy(strategy, now, time_type)
                self.run_records[time_type][date_str].append(strategy.id)

        except Exception as e:
            logger.error(f"Engine run error: {e}")

    def execute_strategy(self, strategy, current_time, time_type):
        """
        执行单个策略代码并落地撮合订单
        """
        from .models import Order, Position, TradeRecord
        from stocks.models import StockData
        from users.models import UserProfile
        from .executor import StrategyExecutor

        try:
            # 1. 获取用户资产基础数据
            user_profile = UserProfile.objects.get(user=strategy.user)

            # 2. 只为当前持仓构建卖出价格快照，避免“全部股票”时无意义的全量查库
            current_position_codes = list(
                Position.objects.filter(user=strategy.user, volume__gt=0).values_list('stock_code', flat=True)
            )

            market_data_dict = {}
            if current_position_codes:
                recent_start = current_time.date() - datetime.timedelta(days=30)
                latest_bars = (
                    StockData.objects
                    .filter(
                        code__in=current_position_codes,
                        date__lte=current_time.date(),
                        date__gte=recent_start
                    )
                    .order_by('code', '-date')
                    .values('code', 'close')
                )

                for bar in latest_bars:
                    code = bar['code']
                    if code not in market_data_dict:
                        market_data_dict[code] = bar['close']

            # 3. 初始化并执行策略
            executor = StrategyExecutor(strategy, user_profile, market_data_dict)
            executor.log(f"--- 触发 {time_type.upper()} (开/尾盘) 时段量化策略 ---")

            orders_to_process = executor.execute()

            if not orders_to_process:
                executor.log("本交易窗口无交易信号产生。")
                return

            # 4. 落地订单与撮合执行
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=strategy.user)

                for order_data in orders_to_process:
                    direction = order_data['direction']
                    code = order_data['code']
                    price = Decimal(str(order_data['price']))
                    volume = int(order_data['volume'])
                    amount = price * volume

                    if direction == 'buy':
                        if profile.balance < amount:
                            executor.log(f"实盘撮合失败: 账户可用资金不足，无法买入 {code} {volume}股")
                            continue

                        profile.balance -= amount
                        profile.save()

                        pos, _ = Position.objects.select_for_update().get_or_create(
                            user=strategy.user,
                            stock_code=code,
                            defaults={'volume': 0, 'avg_price': 0.0, 'frozen_volume': 0}
                        )

                        total_cost = Decimal(str(pos.avg_price)) * pos.volume + amount
                        pos.volume += volume
                        pos.avg_price = float(total_cost / pos.volume)
                        pos.save()

                    elif direction == 'sell':
                        pos = Position.objects.select_for_update().filter(
                            user=strategy.user,
                            stock_code=code
                        ).first()

                        if not pos or pos.volume < volume:
                            executor.log(f"实盘撮合失败: 股票持仓余额不足，无法卖出 {code} {volume}股")
                            continue

                        pos.volume -= volume
                        if pos.volume == 0:
                            pos.avg_price = 0.0
                        pos.save()

                        profile.balance += amount
                        profile.save()

                    new_order = Order.objects.create(
                        user=strategy.user,
                        strategy=strategy,
                        stock_code=code,
                        direction=direction,
                        price=float(price),
                        volume=volume,
                        status='filled',
                        order_time=current_time
                    )

                    TradeRecord.objects.create(
                        order=new_order,
                        stock_code=code,
                        price=float(price),
                        volume=volume,
                        amount=float(amount),
                        fee=0.0,
                        trade_time=current_time
                    )

                    executor.log(f"撮合成交成功: {direction.upper()} {code} {volume}股 @ ￥{price:.2f}")

        except Exception as e:
            logger.error(f"Strategy {strategy.id} execution failed: {e}")