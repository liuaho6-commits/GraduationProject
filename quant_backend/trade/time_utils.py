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
    计算下一个交易时刻 (已移除跳过休市功能，时间将线性自然流逝)
    """
    if isinstance(current_time, str):
        import datetime
        current_time = datetime.datetime.fromisoformat(current_time)

    # 直接返回当前时间，依靠系统的 time_speed 自然往前走，不再做任何空间跳跃
    return current_time