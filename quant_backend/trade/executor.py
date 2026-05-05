import datetime
import json
import logging
import numpy as np
from django.utils import timezone
from .models import Position
from stocks.models import StockData, StockBasicInfo
from .time_utils import get_mock_now
from .factor_config import normalize_strategy_config, get_enabled_factors, max_lookback_for_factors

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

    def _calc_factor(self, closes, factor_code):
        if factor_code == 'mom_20':
            if len(closes) < 21 or not closes[20]:
                return None
            return (closes[0] - closes[20]) / closes[20]

        if factor_code == 'rev_5':
            if len(closes) < 6 or not closes[5]:
                return None
            return -((closes[0] - closes[5]) / closes[5])

        if factor_code == 'vol_20':
            if len(closes) < 21:
                return None
            returns = []
            for idx in range(20):
                prev = closes[idx + 1]
                if not prev:
                    return None
                returns.append((closes[idx] - prev) / prev)
            return -float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0

        if factor_code == 'trend_20':
            if len(closes) < 20:
                return None
            ma20 = sum(closes[:20]) / 20
            return (closes[0] - ma20) / ma20 if ma20 else None

        # 旧版兼容因子
        if factor_code == 'mom_1':
            if len(closes) < 2 or not closes[1]:
                return None
            return (closes[0] - closes[1]) / closes[1]

        if factor_code == 'bias_5':
            if len(closes) < 5:
                return None
            ma5 = sum(closes[:5]) / 5
            return (closes[0] - ma5) / ma5 if ma5 else None

        return None

    def execute(self):
        """核心方法：基于多因子权重进行截面打分并调仓"""
        try:
            # 1. 解析因子参数
            config = normalize_strategy_config(json.loads(self.strategy.code or '{}'))
            enabled_factors = get_enabled_factors(config)
            top_n = int(config.get('top_n', 5))
            buy_threshold = float(config.get('buy_threshold', 0.3))
            allow_cash = bool(config.get('allow_cash', True))
            fee_rate = float(config.get('fee_rate', 0.0001))
            min_fee = float(config.get('min_fee', 0.0))
        except Exception as e:
            self.log(f"策略参数解析失败，请检查配置格式: {e}")
            return []

        if not enabled_factors:
            self.log("未启用任何有效因子，无法执行调仓。")
            return []

        stock_pool = self.get_pool()
        if not stock_pool:
            self.log("股票池为空，无法执行调仓。")
            return []

        self.log(
            f"启动内置多因子评估 | 每日按综合分 Top{top_n} 调仓 "
            f"买入阈值:{buy_threshold}"
        )

        # 2. 批量读取最近一段日线数据，避免“全市场”时逐只查库太慢
        max_lookback = max_lookback_for_factors(enabled_factors)
        recent_start = self.current_time.date() - datetime.timedelta(days=max_lookback * 3)
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
            if len(code_bars) < max_lookback:
                code_bars.append(bar['close'])

        # 3. 计算每只股票的当日因子暴露度
        factor_data = []
        for code in stock_pool:
            closes = bars_map.get(code, [])
            if len(closes) < max_lookback:
                continue

            factor_values = {}
            missing = False
            for factor in enabled_factors:
                value = self._calc_factor(closes, factor['code'])
                if value is None:
                    missing = True
                    break
                factor_values[factor['code']] = value

            if missing:
                continue

            factor_data.append({
                'code': code,
                'price': closes[0],
                'factors': factor_values
            })

        if not factor_data:
            self.log("有效因子数据不足。")
            return []

        # 4. 截面标准化 (Z-Score)
        for item in factor_data:
            item['total_score'] = 0.0

        for factor in enabled_factors:
            code = factor['code']
            values = np.array([x['factors'][code] for x in factor_data], dtype=float)
            mean = np.mean(values)
            std = np.std(values) + 1e-6
            weight = float(factor['weight'])

            for item in factor_data:
                z_value = (item['factors'][code] - mean) / std
                item['total_score'] += z_value * weight

        factor_data.sort(key=lambda x: x['total_score'], reverse=True)
        for index, item in enumerate(factor_data, start=1):
            item['rank'] = index

        candidates = factor_data[:top_n]
        if allow_cash:
            candidates = [item for item in candidates if item['total_score'] >= buy_threshold]
        candidate_codes = {item['code'] for item in candidates}

        self.log(f"今日多因子候选标的: {[x['code'] for x in candidates] or '无，允许空仓'}")

        # ================= 调仓逻辑 =================

        # 6. 卖出逻辑：不在当日 Top N 候选中的持仓清仓
        current_positions = list(Position.objects.filter(user=self.user, volume__gt=0))
        kept_codes = set()
        for pos in current_positions:
            if pos.stock_code not in candidate_codes:
                self.log(f"因子轮动：准备卖出淘汰标的 {pos.stock_code}")
                self.generated_orders.append({
                    'direction': 'sell',
                    'code': pos.stock_code,
                    'price': self.market_data_dict.get(pos.stock_code, pos.avg_price),
                    'volume': pos.volume,
                    'fee_rate': fee_rate,
                    'min_fee': min_fee
                })
            else:
                kept_codes.add(pos.stock_code)

        # 7. 买入逻辑：只买排名 Top N 且分数达标的标的
        buy_targets = [item for item in candidates if item['code'] not in kept_codes]
        available_slots = max(0, top_n - len(kept_codes))
        buy_targets = buy_targets[:available_slots]
        total_cash = float(self.user_profile.balance)
        cash_per_stock = total_cash / len(buy_targets) if buy_targets else 0

        for target in buy_targets:
            code = target['code']
            price = target['price']

            if price > 0:
                estimated_price_with_fee = price * (1 + fee_rate)
                max_shares = int(cash_per_stock / estimated_price_with_fee)
                buy_volume = (max_shares // 100) * 100

                if buy_volume > 0:
                    self.log(f"因子轮动：准备买入入选标的 {code} {buy_volume}股")
                    self.generated_orders.append({
                        'direction': 'buy',
                        'code': code,
                        'price': price,
                        'volume': buy_volume,
                        'fee_rate': fee_rate,
                        'min_fee': min_fee
                    })

        return self.generated_orders
