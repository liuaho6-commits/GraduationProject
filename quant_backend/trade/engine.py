import logging
from django.db import transaction
from .time_utils import get_mock_now

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    交易撮合与策略执行引擎
    """

    def __init__(self):
        pass

    def run_all_active_strategies(self):
        """
        执行所有处于 'active' 状态的策略
        """
        # 🟢 延迟导入
        from .models import Strategy

        try:
            now = get_mock_now()
            # 简单检查：如果是休市时间，理论上不应该运行策略，但在回测模式下可能需要
            if now.hour < 9 or now.hour >= 15:
                return

            active_strategies = Strategy.objects.filter(status='active')
            for strategy in active_strategies:
                self.execute_strategy(strategy, now)

        except Exception as e:
            logger.error(f"Engine run error: {e}")

    def execute_strategy(self, strategy, current_time):
        """
        执行单个策略逻辑
        """
        # 🟢 延迟导入
        from .models import Order, Position
        from stocks.models import StockData

        try:
            # 解析策略代码配置 (假设 stock_pool 是逗号分隔的字符串)
            stock_pool = strategy.stock_pool.split(',') if strategy.stock_pool else []

            # 这里是简单的示例逻辑：如果股票池里的股票涨幅超过3%，就模拟买入
            # 实际项目中，这里会调用 exec() 执行用户编写的 Python 代码

            # 示例：遍历股票池
            for code in stock_pool:
                code = code.strip()
                if not code: continue

                # 获取最新价格
                latest_bar = StockData.objects.filter(code=code, date__lte=current_time.date()).order_by(
                    '-date').first()
                if not latest_bar: continue

                # 简单双均线策略逻辑 (伪代码)
                # if ma5 > ma20 and no_position: buy()
                # if ma5 < ma20 and has_position: sell()

                pass  # 占位，防止具体策略报错，你可以把你的策略代码填在这里

        except Exception as e:
            logger.error(f"Strategy {strategy.id} execution failed: {e}")