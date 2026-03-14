import json
import logging
import numpy as np
from decimal import Decimal
from django.utils import timezone
from .models import Position
from stocks.models import StockData
from .time_utils import get_mock_now

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    多因子实盘执行器：读取因子权重 -> 矩阵打分 -> 自动生成调仓信号
    """

    def __init__(self, strategy, user_profile, market_data_dict):
        self.strategy = strategy
        self.user = strategy.user
        self.user_profile = user_profile
        self.market_data_dict = market_data_dict  # 当前所有股票的最新价 {code: price}
        self.generated_orders = []  # 本次运行产生的订单缓存
        self.logs = []  # 运行日志
        self.current_time = get_mock_now()

    def log(self, msg):
        log_entry = f"[{timezone.now().strftime('%H:%M:%S')}] {msg}"
        self.logs.append(log_entry)
        print(f"Strategy[{self.strategy.name}]: {msg}")

    def get_pool(self):
        if not self.strategy.stock_pool:
            return []
        pool = self.strategy.stock_pool.replace('，', ',')
        return [x.strip() for x in pool.split(',') if x.strip()]

    def execute(self):
        """核心方法：基于多因子权重进行截面打分并调仓"""
        try:
            # 1. 解析因子参数 (复用 code 字段存储 JSON 格式的权重)
            config = json.loads(self.strategy.code)
            weight_mom = float(config.get('weight_mom', 0.5))
            weight_bias = float(config.get('weight_bias', 0.5))
            top_n = int(config.get('top_n', 2))
        except Exception as e:
            self.log(f"策略参数解析失败，请检查配置格式: {e}")
            return []

        stock_pool = self.get_pool()
        if not stock_pool:
            self.log("股票池为空，无法执行调仓。")
            return []

        self.log(f"启动多因子评估 | 动量:{weight_mom} 偏离:{weight_bias} 选股数:Top{top_n}")

        # 2. 计算每只股票的当日因子暴露度 (Factor Exposure)
        factor_data = []
        for code in stock_pool:
            # 获取包含今天在内的过去 6 天数据（用于计算 MA5 和 动量）
            bars = list(StockData.objects.filter(
                code=code,
                date__lte=self.current_time.date()
            ).order_by('-date')[:6])

            if len(bars) < 6:
                continue  # 数据不足无法计算

            close_0 = bars[0].close  # 今日最新价
            close_1 = bars[1].close  # 昨日收盘价
            ma5 = sum(b.close for b in bars[:5]) / 5

            # 因子定义 (与回测引擎保持严格一致)
            momentum = (close_0 - close_1) / close_1 if close_1 else 0
            bias = (close_0 - ma5) / ma5 if ma5 else 0

            factor_data.append({
                'code': code,
                'price': close_0,
                'momentum': momentum,
                'bias': bias
            })

        if not factor_data:
            self.log("有效因子数据不足。")
            return []

        # 3. 截面标准化 (Z-Score) - 矩阵优化核心
        mom_array = np.array([x['momentum'] for x in factor_data])
        bias_array = np.array([x['bias'] for x in factor_data])

        mom_mean, mom_std = np.mean(mom_array), np.std(mom_array) + 1e-6
        bias_mean, bias_std = np.mean(bias_array), np.std(bias_array) + 1e-6

        # 4. 综合打分排序
        for item in factor_data:
            z_mom = (item['momentum'] - mom_mean) / mom_std
            z_bias = (item['bias'] - bias_mean) / bias_std
            item['total_score'] = z_mom * weight_mom + z_bias * weight_bias

        # 降序排列，选出分数最高的 top_n
        factor_data.sort(key=lambda x: x['total_score'], reverse=True)
        target_stocks = factor_data[:top_n]
        target_codes = [x['code'] for x in target_stocks]

        self.log(f"今日多因子优选标的: {target_codes}")

        # ================= 调仓逻辑 =================

        # 5. 卖出逻辑：持仓中不在 target_codes 里的全部清仓
        current_positions = Position.objects.filter(user=self.user, volume__gt=0)
        for pos in current_positions:
            if pos.stock_code not in target_codes:
                self.log(f"因子轮动：准备卖出淘汰标的 {pos.stock_code}")
                self.generated_orders.append({
                    'direction': 'sell',
                    'code': pos.stock_code,
                    'price': self.market_data_dict.get(pos.stock_code, pos.avg_price),
                    'volume': pos.volume
                })

        # 计算现有资产总额（用于等权重分配资金）
        # 简单起见，假设卖出后能拿到全额现金
        total_cash = float(self.user_profile.balance)
        cash_per_stock = total_cash / top_n if top_n > 0 else 0

        # 6. 买入逻辑：买入 target_codes 中的标的
        for target in target_stocks:
            code = target['code']
            price = target['price']

            # 检查是否已经持有
            has_pos = any(p.stock_code == code for p in current_positions)
            if not has_pos and price > 0:
                # 按分配的资金计算可买股数 (向下取整到 100 股的整数倍)
                max_shares = int(cash_per_stock / price)
                buy_volume = (max_shares // 100) * 100

                if buy_volume > 0:
                    self.log(f"因子轮动：准备买入入选标的 {code} {buy_volume}股")
                    self.generated_orders.append({
                        'direction': 'buy',
                        'code': code,
                        'price': price,
                        'volume': buy_volume
                    })

        return self.generated_orders