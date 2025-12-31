import datetime
from django.apps import apps
from django.utils import timezone
from django.conf import settings


def get_mock_now():
    """
    🟢 从数据库 SystemSettings 获取当前模拟时间。
    使用 apps.get_model 避免 models.py 循环引用。
    """
    try:
        # 动态获取模型，防止死锁
        SystemSettings = apps.get_model('trade', 'SystemSettings')

        # 获取第一条设置，如果没有则创建默认值
        setting_obj = SystemSettings.objects.first()
        if not setting_obj:
            # 如果数据库是空的，创建一个默认时间（当前时间）
            setting_obj = SystemSettings.objects.create(
                current_mock_time=timezone.now(),
                time_speed=1.0
            )

        # 返回数据库里的时间
        return setting_obj.current_mock_time
    except Exception as e:
        # 数据库未就绪时的保底方案
        return timezone.now()


def set_mock_now(dt):
    """
    更新数据库中的模拟时间
    """
    try:
        SystemSettings = apps.get_model('trade', 'SystemSettings')
        # 更新第一条记录的时间
        SystemSettings.objects.update(current_mock_time=dt)
    except Exception as e:
        print(f"Error updating system time: {e}")


def get_next_trading_time(current_time):
    """
    计算下一个交易时刻 (跳过休市)
    """
    # 确保是 datetime 对象
    if isinstance(current_time, str):
        current_time = datetime.datetime.fromisoformat(current_time)

    # 1. 周末判断 (weekday: 5=周六, 6=周日)
    if current_time.weekday() >= 5:
        # 如果是周末，跳到下周一 09:30
        days_ahead = 7 - current_time.weekday()  # 周六+2天，周日+1天
        next_day = current_time + datetime.timedelta(days=days_ahead)
        return next_day.replace(hour=9, minute=30, second=0, microsecond=0)

    # 定义当日关键时间点
    t0930 = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    t1130 = current_time.replace(hour=11, minute=30, second=0, microsecond=0)
    t1300 = current_time.replace(hour=13, minute=0, second=0, microsecond=0)
    t1500 = current_time.replace(hour=15, minute=0, second=0, microsecond=0)

    # 2. 盘前 (00:00 - 09:30) -> 跳到 09:30
    if current_time < t0930:
        return t0930

    # 3. 午休 (11:30 - 13:00) -> 跳到 13:00
    if t1130 <= current_time < t1300:
        return t1300

    # 4. 盘后 (>= 15:00) -> 跳到次日 09:30
    if current_time >= t1500:
        next_day = current_time + datetime.timedelta(days=1)
        return get_next_trading_time(next_day.replace(hour=9, minute=30, second=0))

    # 交易时间，保持不变
    return current_time