import logging
import datetime
from django.utils import timezone
from django.db import transaction
from .engine import TradingEngine
from .time_utils import get_mock_now, set_mock_now, get_next_trading_time

logger = logging.getLogger(__name__)

# 全局单例引擎
engine = TradingEngine()


def clock_tick():
    """
    系统时钟心跳：
    1. 读取数据库时间
    2. 增加时间
    3. 跳过休市
    4. 写回数据库
    """
    # 🟢 延迟导入，防止循环引用
    from .models import SystemSettings

    try:
        # 获取配置（不使用缓存，直接查库确保实时性）
        settings = SystemSettings.objects.first()
        if not settings:
            return

        # 如果倍速 <= 0，暂停时间流逝
        if settings.time_speed <= 0:
            return

        # 1. 获取当前“上帝时间”
        now = settings.current_mock_time

        # 2. 计算流逝后的新时间
        delta = datetime.timedelta(seconds=settings.time_speed)
        new_time = now + delta

        # 3. 判断是否需要触发收盘结算 (跨越 15:00)
        if now.hour < 15 and (new_time.hour >= 15 or new_time.day > now.day):
            record_daily_performance()

        # 4. 应用跳过休市逻辑
        if settings.skip_non_trading:
            valid_time = get_next_trading_time(new_time)
        else:
            valid_time = new_time

        # 5. 写回数据库 (更新上帝时间)
        # update 比 save 更快且线程安全
        SystemSettings.objects.filter(id=settings.id).update(current_mock_time=valid_time)

        # 6. 触发策略
        run_active_strategies()

    except Exception as e:
        print(f"Clock tick warning: {e}")


def run_active_strategies():
    if engine:
        engine.run_all_active_strategies()


def record_daily_performance():
    """
    每日收盘结算逻辑
    """
    from django.contrib.auth.models import User
    from .models import DailyPerformance, Position
    from stocks.models import StockData
    from users.models import UserProfile

    # 使用当前的模拟时间进行结算
    current_mock_time = get_mock_now()
    today = current_mock_time.date()

    users = User.objects.all()
    for user in users:
        try:
            with transaction.atomic():
                try:
                    profile = user.userprofile
                except UserProfile.DoesNotExist:
                    continue

                # 资金与持仓
                balance = float(profile.balance)
                initial_capital = float(profile.initial_capital) if profile.initial_capital > 0 else 200000.0

                positions = Position.objects.filter(user=user)
                market_value = 0.0

                for pos in positions:
                    # 获取该股票在“上帝时间”之前的最新价格
                    latest_price_obj = StockData.objects.filter(
                        code=pos.stock_code,
                        date__lte=today
                    ).order_by('-date').first()

                    price = float(latest_price_obj.close) if latest_price_obj else pos.avg_price
                    market_value += price * pos.volume

                total_assets = balance + market_value

                # 计算收益
                total_profit = total_assets - initial_capital
                total_return_rate = (total_profit / initial_capital * 100) if initial_capital > 0 else 0

                # 计算日收益 (相比昨日)
                yesterday_perf = DailyPerformance.objects.filter(
                    user=user,
                    date__lt=today
                ).order_by('-date').first()

                day_profit = 0
                if yesterday_perf:
                    day_profit = total_assets - float(yesterday_perf.total_assets)

                # 存入数据库
                DailyPerformance.objects.update_or_create(
                    user=user,
                    date=today,
                    defaults={
                        'total_assets': total_assets,
                        'day_profit': day_profit,
                        'total_return_rate': total_return_rate,
                        'day_return_rate': 0  # 简化
                    }
                )
        except Exception as e:
            print(f"结算失败 {user.username}: {e}")