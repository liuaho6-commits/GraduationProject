from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.apps import apps
from decimal import Decimal


# ================= 1. 策略模型 =================
class Strategy(models.Model):
    STATUS_CHOICES = (
        ('active', '运行中'),
        ('paused', '已暂停'),
        ('stopped', '已停止'),
    )
    stock_pool = models.TextField(blank=True, default='', verbose_name="股票池", help_text="英文逗号分隔")
    total_return = models.FloatField(default=0.0, verbose_name="总收益率")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="所属用户")
    name = models.CharField(max_length=100, verbose_name="策略名称")
    code = models.TextField(verbose_name="策略代码")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='stopped', verbose_name="状态")

    class Meta:
        verbose_name = "量化策略"
        verbose_name_plural = verbose_name
        db_table = 'trade_strategy'

    def __str__(self):
        return f"{self.user.username} - {self.name}"


# ================= 2. 持仓模型 =================
class Position(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    stock_code = models.CharField(max_length=20, verbose_name="股票代码")
    volume = models.IntegerField(default=0, verbose_name="持仓股数")
    avg_price = models.FloatField(default=0.0, verbose_name="持仓均价")
    frozen_volume = models.IntegerField(default=0, verbose_name="冻结股数")

    class Meta:
        unique_together = ('user', 'stock_code')
        verbose_name = "用户持仓"
        verbose_name_plural = verbose_name
        db_table = 'trade_position'


# ================= 3. 订单模型 =================
class Order(models.Model):
    ORDER_TYPE = (('buy', '买入'), ('sell', '卖出'))
    STATUS_CHOICES = (('pending', '待成交'), ('filled', '已成交'), ('canceled', '已撤单'), ('failed', '失败'))

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    strategy = models.ForeignKey(Strategy, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联策略")
    stock_code = models.CharField(max_length=20, verbose_name="股票代码")
    direction = models.CharField(max_length=5, choices=ORDER_TYPE, verbose_name="买卖方向")
    price = models.FloatField(verbose_name="委托价格")
    volume = models.IntegerField(verbose_name="委托数量")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    order_time = models.DateTimeField(verbose_name="委托时间")

    class Meta:
        verbose_name = "委托订单"
        verbose_name_plural = verbose_name
        db_table = 'trade_order'


# ================= 4. 成交记录 =================
class TradeRecord(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, verbose_name="关联订单")
    stock_code = models.CharField(max_length=20, verbose_name="股票代码")
    price = models.FloatField(verbose_name="成交均价")
    volume = models.IntegerField(verbose_name="成交数量")
    amount = models.FloatField(verbose_name="成交金额")
    fee = models.FloatField(default=0.0, verbose_name="手续费")
    trade_time = models.DateTimeField(verbose_name="成交时间")

    class Meta:
        verbose_name = "成交记录"
        verbose_name_plural = verbose_name
        db_table = 'trade_record'


# ================= 5. 日收益统计 =================
class DailyPerformance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    date = models.DateField(verbose_name="日期")
    total_assets = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="当日总资产")
    day_profit = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="当日收益")
    day_return_rate = models.FloatField(verbose_name="当日收益率")
    total_return_rate = models.FloatField(verbose_name="累计收益率")

    class Meta:
        verbose_name = "日收益统计"
        verbose_name_plural = verbose_name
        db_table = 'trade_daily_performance'
        unique_together = ('user', 'date')


# ================= 6. 日内5分钟收益 =================
class IntradayPerformance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    time = models.DateTimeField(verbose_name="时间点")
    total_assets = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="瞬时总资产")
    total_return_rate = models.FloatField(verbose_name="瞬时累计收益率")

    class Meta:
        verbose_name = "日内5分钟走势"
        verbose_name_plural = verbose_name
        db_table = 'trade_intraday_performance'
        indexes = [models.Index(fields=['user', 'time'])]


# ================= 7. 系统全局设置 =================
class SystemSettings(models.Model):
    current_mock_time = models.DateTimeField(verbose_name="当前模拟时间", default=timezone.now)
    time_speed = models.FloatField(verbose_name="时间流速倍率", default=1.0)
    skip_non_trading = models.BooleanField(verbose_name="自动跳过休市", default=False)
    last_update_time = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "系统上帝设置"
        verbose_name_plural = verbose_name
        db_table = 'system_settings'

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return f"系统时间控制 (当前: {self.current_mock_time})"

    def hard_reset_world(self):
        """
        公开的核弹级重置方法，仅在显式调用时执行
        """
        Order = apps.get_model('trade', 'Order')
        Position = apps.get_model('trade', 'Position')
        DailyPerformance = apps.get_model('trade', 'DailyPerformance')
        IntradayPerformance = apps.get_model('trade', 'IntradayPerformance')
        UserProfile = apps.get_model('users', 'UserProfile')

        print(f"\n☢️ [God Mode] EXECUTE HARD RESET (Time Travel Initiated) ☢️")

        print(f"⚠️ Clearing all trade data...")
        Order.objects.all().delete()
        Position.objects.all().delete()
        DailyPerformance.objects.all().delete()
        IntradayPerformance.objects.all().delete()

        print(f"⚠️ Resetting user balances...")
        default_cap = Decimal('200000.00')

        # 使用 UserProfile.objects.all() 自动忽略无 Profile 的脏数据
        for profile in UserProfile.objects.all():
            profile.initial_capital = default_cap
            profile.balance = default_cap
            if hasattr(profile, 'withdrawable_cash'):
                profile.withdrawable_cash = default_cap

            profile.last_market_value = 0
            profile.last_total_assets = default_cap
            profile.daily_profit = 0
            profile.total_profit = 0

            profile.save()
            print(f"   User {profile.user.username}: Factory reset to {default_cap}")

        print(f"✅ World reset complete.\n")


# ================= 8. 拆分出的代理模型 =================
class TimeFlowSettings(SystemSettings):
    """用于调整流速 (安全)"""
    class Meta:
        proxy = True  # 关键：这是一个代理模型，不创建新表
        verbose_name = "1. 时间流速控制 (安全)"
        verbose_name_plural = verbose_name

class TimeResetSettings(SystemSettings):
    """用于穿越时间 (危险)"""
    class Meta:
        proxy = True
        verbose_name = "2. 时间穿越 & 重置 (危险)"
        verbose_name_plural = verbose_name