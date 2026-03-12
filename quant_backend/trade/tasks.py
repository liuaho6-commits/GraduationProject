import logging
import datetime
from decimal import Decimal
from django.utils import timezone
from .engine import TradingEngine
from .time_utils import get_next_trading_time

logger = logging.getLogger(__name__)

engine = TradingEngine()


def clock_tick():
    """
    系统时钟心跳
    """
    from .models import SystemSettings

    try:
        settings = SystemSettings.objects.first()
        if not settings or settings.time_speed <= 0:
            return

        now = settings.current_mock_time
        delta = datetime.timedelta(seconds=settings.time_speed)
        new_time = now + delta

        # 触发分时快照
        if new_time.minute != now.minute and new_time.minute % 5 == 0:
            record_intraday_snapshot(new_time)

        # 触发收盘结算
        if now.hour < 15 and (new_time.hour >= 15 or new_time.date() > now.date()):
            print(f"🏁 [Settlement] Daily settlement for {now.date()}...")
            record_daily_performance()

        # 🔴 修复点：移除了 settings.skip_non_trading 的判断逻辑，直接使用计算出的新时间
        valid_time = new_time

        # 更新时间 (使用 update 不会触发 save/重置)
        SystemSettings.objects.filter(id=settings.id).update(current_mock_time=valid_time)

        # 撮合
        if engine:
            engine.run_all_active_strategies()

    except Exception as e:
        print(f"Clock tick error: {e}")


def record_intraday_snapshot(current_time):
    """
    记录日内分时资产 (快照)
    🟢 修正：遍历 UserProfile 而不是 User，避免 'User has no profile' 错误
    """
    from .models import IntradayPerformance, Position
    from users.models import UserProfile
    from stocks.models import StockMinuteData, StockData

    # 直接获取所有 Profile，包含关联的 User
    profiles = UserProfile.objects.select_related('user').all()

    for profile in profiles:
        user = profile.user
        try:
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
            continue


def record_daily_performance():
    """
    每日收盘结算
    🟢 修正：遍历 UserProfile 而不是 User
    """
    from .models import DailyPerformance, IntradayPerformance
    from users.models import UserProfile
    from .time_utils import get_mock_now

    current_mock_time = get_mock_now()
    today = current_mock_time.date()

    # 直接获取所有 Profile
    profiles = UserProfile.objects.select_related('user').all()

    for profile in profiles:
        user = profile.user
        try:
            # 1. 触发资产更新
            profile.update_asset_cache()

            total_assets = profile.last_total_assets
            total_profit = profile.total_profit

            # 2. 计算日收益
            yesterday_perf = DailyPerformance.objects.filter(
                user=user, date__lt=today
            ).order_by('-date').first()

            day_profit = Decimal('0.00')
            prev_assets = profile.initial_capital

            if yesterday_perf:
                day_profit = total_assets - yesterday_perf.total_assets
                prev_assets = yesterday_perf.total_assets
            else:
                day_profit = total_profit

            day_return_rate = 0.0
            if prev_assets > 0:
                day_return_rate = float((day_profit / prev_assets) * 100)

            # 3. 存盘
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

            # 4. 清理旧数据
            IntradayPerformance.objects.filter(
                user=user,
                time__date__lt=today
            ).delete()

        except Exception as e:
            print(f"Settlement failed for {user.username}: {e}")