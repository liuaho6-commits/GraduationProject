import datetime
import json
import logging
import numpy as np
from django.utils import timezone
from .models import Position
from stocks.models import StockData, StockBasicInfo
from .time_utils import get_mock_now

logger = logging.getLogger(__name__)

ALL_STOCK_POOL_MARKERS = {'__ALL__', 'ALL', 'ALL_STOCKS', '全部', '全部股票'}


class StrategyExecutor:
    """
    多因子实盘执行器：读取因子权重 -> 矩阵打分 -> 自动生成调仓信号
    """

    def __init__(self, strategy, user_profile, market_data_dict):
        self.strategy = strategy
        self.user = strategy.user
        self.user_profile = user_profile
        self.market_data_dict = market_data_dict  # 当前持仓股票的最新价 {code: price}
        self.generated_orders = []  # 本次运行产生的订单缓存
        self.logs = []  # 运行日志
        self.current_time = get_mock_now()

    def log(self, msg):
        log_entry = f"[{timezone.now().strftime('%H:%M:%S')}] {msg}"
        self.logs.append(log_entry)
        print(f"Strategy[{self.strategy.name}]: {msg}")

    def _is_all_stock_pool(self, raw_value):
        return str(raw_value).strip().upper() in ALL_STOCK_POOL_MARKERS

    def _get_all_stock_codes(self):
        codes = list(
            StockBasicInfo.objects.order_by('code').values_list('code', flat=True)
        )
        if codes:
            return codes

        return list(
            StockData.objects.values_list('code', flat=True).distinct()
        )

    def get_pool(self):
        raw_pool = str(self.strategy.stock_pool or '').strip()
        if not raw_pool:
            return []

        if self._is_all_stock_pool(raw_pool):
            all_codes = self._get_all_stock_codes()
            if all_codes:
                self.log(f"已启用全部股票模式，共载入 {len(all_codes)} 只股票")
            else:
                self.log("已选择全部股票，但系统中没有可用股票数据。")
            return all_codes

        normalized = raw_pool.replace('，', ',').replace('\n', ',')
        result = []
        seen = set()

        for item in normalized.split(','):
            code = item.strip()
            if code and code not in seen:
                seen.add(code)
                result.append(code)

        return result

    def execute(self):
        """核心方法：基于多因子权重进行截面打分并调仓"""
        try:
            # 1. 解析因子参数
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

        # 2. 批量读取最近 30 天内的数据，避免“全市场”时逐只查库太慢
        recent_start = self.current_time.date() - datetime.timedelta(days=30)
        recent_bars = (
            StockData.objects
            .filter(
                code__in=stock_pool,
                date__lte=self.current_time.date(),
                date__gte=recent_start
            )
            .order_by('code', '-date')
            .values('code', 'close')
        )

        bars_map = {}
        for bar in recent_bars:
            code = bar['code']
            code_bars = bars_map.setdefault(code, [])
            if len(code_bars) < 6:
                code_bars.append(bar['close'])

        # 3. 计算每只股票的当日因子暴露度
        factor_data = []
        for code in stock_pool:
            closes = bars_map.get(code, [])
            if len(closes) < 6:
                continue

            close_0 = closes[0]  # 今日最新价
            close_1 = closes[1]  # 昨日收盘价
            ma5 = sum(closes[:5]) / 5

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

        # 4. 截面标准化 (Z-Score)
        mom_array = np.array([x['momentum'] for x in factor_data])
        bias_array = np.array([x['bias'] for x in factor_data])

        mom_mean, mom_std = np.mean(mom_array), np.std(mom_array) + 1e-6
        bias_mean, bias_std = np.mean(bias_array), np.std(bias_array) + 1e-6

        # 5. 综合打分排序
        for item in factor_data:
            z_mom = (item['momentum'] - mom_mean) / mom_std
            z_bias = (item['bias'] - bias_mean) / bias_std
            item['total_score'] = z_mom * weight_mom + z_bias * weight_bias

        factor_data.sort(key=lambda x: x['total_score'], reverse=True)
        target_stocks = factor_data[:top_n]
        target_codes = [x['code'] for x in target_stocks]

        self.log(f"今日多因子优选标的: {target_codes}")

        # ================= 调仓逻辑 =================

        # 6. 卖出逻辑：持仓中不在 target_codes 里的全部清仓
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

        # 7. 买入逻辑：买入 target_codes 中的标的
        total_cash = float(self.user_profile.balance)
        cash_per_stock = total_cash / top_n if top_n > 0 else 0

        for target in target_stocks:
            code = target['code']
            price = target['price']

            has_pos = any(p.stock_code == code for p in current_positions)
            if not has_pos and price > 0:
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