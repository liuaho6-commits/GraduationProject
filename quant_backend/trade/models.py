from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


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
    order_time = models.DateTimeField(verbose_name="委托时间")  # 移除了 auto_now_add 以便支持时光机

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
    trade_time = models.DateTimeField(verbose_name="成交时间")  # 同样移除 auto_now_add

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


# ================= 🟢 8. 上帝模式：时光倒流自动清洗信号 =================
@receiver(post_save, sender=SystemSettings)
def on_time_travel_cleanup(sender, instance, **kwargs):
    """
    当在 Admin 后台手动修改系统时间时触发。
    自动删除所有“未来”的订单和收益记录，防止穿越导致的余额错误。
    """
    # 1. 获取新设置的时间
    god_time = instance.current_mock_time

    print(f"\n⚡⚡⚡ [God Mode] 检测到时间变更至 {god_time} ⚡⚡⚡")
    print(f"正在清洗未来数据...")

    # 2. 删除未来订单 (级联删除 TradeRecord)
    orders_deleted, _ = Order.objects.filter(order_time__gt=god_time).delete()
    if orders_deleted > 0:
        print(f"   >>> 已删除未来订单: {orders_deleted} 条")

    # 3. 删除未来日收益记录
    # 转换 datetime 为 date 进行比较
    god_date = god_time.date()
    daily_deleted, _ = DailyPerformance.objects.filter(date__gt=god_date).delete()
    if daily_deleted > 0:
        print(f"   >>> 已删除未来日报: {daily_deleted} 条")

    print(f"清洗完成。现在是纯净的 {god_time}。\n")