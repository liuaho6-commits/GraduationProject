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
        # 🟢 关键修复：记录策略执行状态，防止同一窗口被系统秒级时钟多次触发
        # 数据结构: {'open': {'2026-01-07': [strategy_id_1, strategy_id_2]}, 'close': {...}}
        self.run_records = {'open': {}, 'close': {}}

    def run_all_active_strategies(self):
        """
        执行所有处于 'active' 状态的策略
        """
        from .models import Strategy

        try:
            # 1. 严格使用你原有的模拟时间（原汁原味，不加任何时区转换干预）
            now = get_mock_now()
            date_str = now.strftime('%Y-%m-%d')

            # 2. 判定当前是开盘还是尾盘阶段 (日频交易规则)
            time_type = None

            # 开盘时段：09:30 - 09:35 (在这个区间内只执行一次)
            if now.hour == 9 and 30 <= now.minute <= 35:
                time_type = 'open'
            # 尾盘时段：14:50 - 14:59
            elif now.hour == 14 and 50 <= now.minute <= 59:
                time_type = 'close'

            # 既不是开盘也不是尾盘，跳过
            if not time_type:
                return

            # 初始化今日的执行记录缓存字典
            if date_str not in self.run_records[time_type]:
                self.run_records[time_type][date_str] = []

            # 获取活跃策略
            active_strategies = Strategy.objects.filter(status='active').select_related('user')

            for strategy in active_strategies:
                # 3. 防止高频重复执行：检查该策略今天在这个窗口是否已经执行过
                if strategy.id in self.run_records[time_type][date_str]:
                    continue

                # 4. 执行策略！
                self.execute_strategy(strategy, now, time_type)

                # 5. 登记造册，锁死该策略在当前时段的执行权限
                self.run_records[time_type][date_str].append(strategy.id)

        except Exception as e:
            logger.error(f"Engine run error: {e}")

    def execute_strategy(self, strategy, current_time, time_type):
        """
        执行单个策略代码并落地撮合订单 (带资金原子事务)
        """
        from .models import Order, Position, TradeRecord
        from stocks.models import StockData
        from users.models import UserProfile
        from .executor import StrategyExecutor

        try:
            # 1. 获取用户资产基础数据
            user_profile = UserProfile.objects.get(user=strategy.user)

            # 2. 准备股票池和当日行情快照字典
            stock_pool = strategy.stock_pool.split(',') if strategy.stock_pool else []
            stock_pool = [code.strip() for code in stock_pool if code.strip()]

            market_data_dict = {}
            for code in stock_pool:
                # 获取该股票当前可用的最新一条日线数据作为价格基准
                latest_bar = StockData.objects.filter(
                    code=code,
                    date__lte=current_time.date()
                ).order_by('-date').first()

                if latest_bar:
                    market_data_dict[code] = latest_bar.close

            # 3. 初始化并唤醒执行器，运行用户的 Python 策略代码
            executor = StrategyExecutor(strategy, user_profile, market_data_dict)
            executor.log(f"--- 触发 {time_type.upper()} (开/尾盘) 时段量化策略 ---")

            orders_to_process = executor.execute()

            # 如果用户代码没有触发任何买卖动作，直接结束
            if not orders_to_process:
                executor.log("本交易窗口无交易信号产生。")
                return

            # 4. 落地订单与撮合执行 (🔥 核心：使用事务保证资金不超卖不丢失)
            with transaction.atomic():
                # select_for_update 强制上悲观锁，防止秒级高频调用篡改资金
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

                        # 扣除余额
                        profile.balance -= amount
                        profile.save()

                        # 增加持仓
                        pos, created = Position.objects.select_for_update().get_or_create(
                            user=strategy.user,
                            stock_code=code,
                            defaults={'volume': 0, 'avg_price': 0.0, 'frozen_volume': 0}
                        )
                        # 摊薄计算持仓均价
                        total_cost = Decimal(str(pos.avg_price)) * pos.volume + amount
                        pos.volume += volume
                        pos.avg_price = float(total_cost / pos.volume)
                        pos.save()

                    elif direction == 'sell':
                        pos = Position.objects.select_for_update().filter(user=strategy.user, stock_code=code).first()
                        if not pos or pos.volume < volume:
                            executor.log(f"实盘撮合失败: 股票持仓余额不足，无法卖出 {code} {volume}股")
                            continue

                        # 减除持仓
                        pos.volume -= volume
                        if pos.volume == 0:
                            pos.avg_price = 0.0
                        pos.save()

                        # 退回余额
                        profile.balance += amount
                        profile.save()

                    # 生成系统委托单记录
                    new_order = Order.objects.create(
                        user=strategy.user,
                        strategy=strategy,
                        stock_code=code,
                        direction=direction,
                        price=float(price),
                        volume=volume,
                        status='filled',  # 市价秒级撮合，直接标记为填满
                        order_time=current_time
                    )

                    # 生成系统资金流水记录
                    TradeRecord.objects.create(
                        order=new_order,
                        stock_code=code,
                        price=float(price),
                        volume=volume,
                        amount=float(amount),
                        fee=0.0,  # 毕业设计要求里模拟盘先不扣除万二佣金
                        trade_time=current_time
                    )
                    executor.log(f"撮合成交成功: {direction.upper()} {code} {volume}股 @ ￥{price:.2f}")

        except Exception as e:
            logger.error(f"Strategy {strategy.id} execution failed: {e}")