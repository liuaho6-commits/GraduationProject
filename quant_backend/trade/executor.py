import logging
import traceback
import sys
from io import StringIO
from decimal import Decimal
from django.utils import timezone
from .models import Order, Position

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    策略执行器：负责运行单个策略的 Python 代码
    """

    def __init__(self, strategy, user_profile, market_data_dict):
        self.strategy = strategy
        self.user = strategy.user
        self.user_profile = user_profile
        self.market_data_dict = market_data_dict  # 当前所有股票的最新价 {code: price}
        self.generated_orders = []  # 本次运行产生的订单缓存
        self.logs = []  # 运行日志

    def log(self, msg):
        """注入给策略的 log 函数"""
        log_entry = f"[{timezone.now().strftime('%H:%M:%S')}] {msg}"
        self.logs.append(log_entry)
        # 也可以选择存入数据库或打印到控制台
        print(f"Strategy[{self.strategy.name}]: {msg}")

    def get_price(self, code):
        """注入给策略的 get_price 函数"""
        return self.market_data_dict.get(code, 0.0)

    def get_pool(self):
        """注入给策略的 get_pool 函数"""
        if not self.strategy.stock_pool:
            return []
        # 处理中文或英文逗号
        pool = self.strategy.stock_pool.replace('，', ',')
        return [x.strip() for x in pool.split(',') if x.strip()]

    def buy(self, code, volume):
        """注入给策略的 buy 函数"""
        price = self.get_price(code)
        if price <= 0:
            self.log(f"错误: 股票 {code} 无最新价格，无法买入")
            return

        cost = Decimal(str(price)) * Decimal(volume)
        # 简单预校验：检查余额是否足够 (模拟盘暂不计算手续费，或者之后在 Engine 层统一算)
        if self.user_profile.balance < cost:
            self.log(f"资金不足: 需 {cost:.2f}, 只有 {self.user_profile.balance:.2f}, 无法买入 {code}")
            return

        # 生成待处理订单 (暂不存库，等 Engine 统一处理)
        self.generated_orders.append({
            'direction': 'buy',
            'code': code,
            'price': price,
            'volume': int(volume)
        })
        self.log(f"生成买单: {code} {volume}股 @ {price:.2f}")

    def sell(self, code, volume):
        """注入给策略的 sell 函数"""
        # 查持仓
        position = Position.objects.filter(user=self.user, stock_code=code).first()
        if not position or position.volume < volume:
            self.log(f"持仓不足: {code} 现有 {position.volume if position else 0}, 欲卖 {volume}")
            return

        price = self.get_price(code)
        self.generated_orders.append({
            'direction': 'sell',
            'code': code,
            'price': price,
            'volume': int(volume)
        })
        self.log(f"生成卖单: {code} {volume}股 @ {price:.2f}")

    def execute(self):
        """核心方法：执行用户代码"""
        code_str = self.strategy.code

        # 1. 准备全局上下文 (注入函数)
        scope = {
            'get_price': self.get_price,
            'get_pool': self.get_pool,
            'buy': self.buy,
            'sell': self.sell,
            'log': self.log,
            'context': {}  # 可供用户存临时变量
        }

        try:
            # 2. 编译并执行代码
            # 注意：exec 在生产环境有安全风险，毕设或内网项目通常可以接受
            exec(code_str, scope)

            # 3. 调用入口函数 handle_bar
            if 'handle_bar' in scope:
                scope['handle_bar']()
            else:
                self.log("错误: 策略代码中未找到 handle_bar() 函数")

        except Exception as e:
            error_msg = traceback.format_exc()
            self.log(f"策略运行异常: {e}")
            logger.error(f"Strategy {self.strategy.id} Error: {error_msg}")

        return self.generated_orders