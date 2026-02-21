import logging
import datetime
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from .engine import TradingEngine
from .time_utils import get_mock_now, get_next_trading_time

logger = logging.getLogger(__name__)

engine = TradingEngine()


def clock_tick():
    """
    系统时钟心跳：驱动时间流逝、触发撮合、触发定时快照
    """
    from .models import SystemSettings

    try:
        settings = SystemSettings.objects.first()
        if not settings or settings.time_speed <= 0:
            return

        # 1. 时间流逝
        now = settings.current_mock_time
        delta = datetime.timedelta(seconds=settings.time_speed)
        new_time = now + delta

        # 2. 触发分时快照 (Intraday Snapshot)
        if new_time.minute != now.minute and new_time.minute % 5 == 0:
            # print(f"📸 [Snapshot] Recording intraday assets at {new_time.strftime('%H:%M')}...")
            record_intraday_snapshot(new_time)

        # 3. 触发收盘结算 (15:00)
        # 这里的逻辑是：如果跨越了15点，或者跨越了日期（针对跳过休市的情况）
        if now.hour < 15 and (new_time.hour >= 15 or new_time.date() > now.date()):
            print(f"🏁 [Settlement] Daily settlement for {now.date()}...")
            record_daily_performance()

        # 4. 跳过休市
        if settings.skip_non_trading:
            valid_time = get_next_trading_time(new_time)
        else:
            valid_time = new_time

        # 5. 更新时间
        SystemSettings.objects.filter(id=settings.id).update(current_mock_time=valid_time)

        # 6. 撮合交易
        if engine:
            engine.run_all_active_strategies()

    except Exception as e:
        print(f"Clock tick error: {e}")


def record_intraday_snapshot(current_time):
    """
    记录日内分时资产 (快照)
    """
    from django.contrib.auth.models import User
    from .models import IntradayPerformance, Position
    from users.models import UserProfile
    from stocks.models import StockMinuteData, StockData

    users = User.objects.all()
    for user in users:
        try:
            profile = user.profile  # 注意：Django反向查询通常是 user.profile (取决于 related_name)
            # 如果 related_name='profile'，则用 user.profile。如果是默认，可能是 user.userprofile
            # 根据 models.py 定义: user = models.OneToOneField(..., related_name='profile')

            positions = Position.objects.filter(user=user, volume__gt=0)
            market_value = Decimal('0.00')

            for pos in positions:
                price = Decimal(str(pos.avg_price))
                m_data = StockMinuteData.objects.filter(
                    code=pos.stock_code,
                    date__lte=current_time
                ).order_by('-date').only('close').first()

                if m_data:
                    price = Decimal(str(m_data.close))
                else:
                    d_data = StockData.objects.filter(
                        code=pos.stock_code,
                        date__lte=current_time.date()
                    ).order_by('-date').only('close').first()
                    if d_data:
                        price = Decimal(str(d_data.close))

                market_value += price * Decimal(str(pos.volume))

            total_assets = profile.balance + market_value

            base = profile.initial_capital
            ret_rate = ((total_assets - base) / base * 100) if base > 0 else 0

            IntradayPerformance.objects.update_or_create(
                user=user,
                time=current_time,
                defaults={
                    'total_assets': total_assets,
                    'total_return_rate': ret_rate
                }
            )

        except Exception as e:
            # print(f"Snapshot error for user {user.id}: {e}")
            continue


def record_daily_performance():
    """
    每日收盘结算：记录总资产、日收益、日收益率
    """
    from django.contrib.auth.models import User
    from .models import DailyPerformance, Position, IntradayPerformance
    from users.models import UserProfile
    from stocks.models import StockData, StockMinuteData
    from .time_utils import get_mock_now

    current_mock_time = get_mock_now()
    today = current_mock_time.date()

    users = User.objects.all()
    for user in users:
        try:
            profile = user.profile  # 使用 related_name='profile'

            # 1. 触发一次精确的资产更新
            profile.update_asset_cache()

            total_assets = profile.last_total_assets
            total_profit = profile.total_profit

            # 2. 计算日收益
            yesterday_perf = DailyPerformance.objects.filter(
                user=user, date__lt=today
            ).order_by('-date').first()

            day_profit = Decimal('0.00')
            prev_assets = profile.initial_capital  # 默认基准为初始本金

            if yesterday_perf:
                day_profit = total_assets - yesterday_perf.total_assets
                prev_assets = yesterday_perf.total_assets
            else:
                # 第一天交易，日收益 = 总收益
                day_profit = total_profit

            # 3. 计算当日收益率 (Day Return Rate)
            # 公式：当日收益 / 昨日总资产 * 100%
            day_return_rate = 0.0
            if prev_assets > 0:
                day_return_rate = float((day_profit / prev_assets) * 100)

            # 4. 存盘
            DailyPerformance.objects.update_or_create(
                user=user,
                date=today,
                defaults={
                    'total_assets': total_assets,
                    'day_profit': day_profit,
                    'total_return_rate': (float(total_profit) / float(
                        profile.initial_capital) * 100) if profile.initial_capital else 0,
                    'day_return_rate': day_return_rate
                }
            )

            # 5. 清理旧的分时数据 (可选，防止数据库爆炸)
            IntradayPerformance.objects.filter(
                user=user,
                time__date__lt=today
            ).delete()

        except Exception as e:
            print(f"Settlement failed for {user.username}: {e}")