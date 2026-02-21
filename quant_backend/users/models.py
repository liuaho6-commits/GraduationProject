from django.db import models
from django.contrib.auth.models import User
from django.apps import apps
from django.utils import timezone
from decimal import Decimal


# ================= 1. 用户扩展信息 (钱包/头像等) =================
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="关联账户")
    phone = models.CharField(max_length=11, blank=True, null=True, verbose_name="手机号")
    avatar = models.CharField(max_length=300, blank=True, null=True,
                              default='https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
                              verbose_name="头像URL")

    # 核心字段
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="可用余额")
    withdrawable_cash = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="可取资金")
    initial_capital = models.DecimalField(max_digits=14, decimal_places=2, default=200000.00, verbose_name="初始本金")

    # 缓存字段（高性能读取）
    last_market_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="总市值")
    last_total_assets = models.DecimalField(max_digits=14, decimal_places=2, default=200000.00, verbose_name="总资产")
    daily_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="当日收益")
    total_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="总收益")

    last_update_time = models.DateTimeField(auto_now=True, verbose_name="最后更新时间")

    class Meta:
        db_table = 'user_profile'

    def update_asset_cache(self):
        """核心计算逻辑：更新总资产、市值、收益等"""
        # 动态导入避免循环依赖
        Position = apps.get_model('trade', 'Position')
        SystemSettings = apps.get_model('trade', 'SystemSettings')
        StockMinuteData = apps.get_model('stocks', 'StockMinuteData')
        StockData = apps.get_model('stocks', 'StockData')
        DailyPerformance = apps.get_model('trade', 'DailyPerformance')

        settings = SystemSettings.objects.first()
        current_time = settings.current_mock_time if settings else timezone.now()

        # 1. 计算总市值
        market_value = Decimal('0.0')
        positions = Position.objects.filter(user=self.user, volume__gt=0)

        for pos in positions:
            # 获取最新价（优先分时，其次日线）
            price = Decimal('0.0')
            # 尝试获取当前时刻之前的最新分时数据
            m_data = StockMinuteData.objects.filter(
                code=pos.stock_code,
                date__lte=current_time
            ).order_by('-date').only('close').first()

            if m_data:
                price = Decimal(str(m_data.close))
            else:
                # 如果没有分时数据，尝试获取日线数据
                d_data = StockData.objects.filter(
                    code=pos.stock_code,
                    date__lte=current_time.date()
                ).order_by('-date').only('close').first()
                price = Decimal(str(d_data.close)) if d_data else Decimal(str(pos.avg_price))

            market_value += Decimal(pos.volume) * price

        # 2. 计算各项指标
        self.last_market_value = market_value
        self.last_total_assets = self.balance + market_value
        self.total_profit = self.last_total_assets - self.initial_capital

        # 3. 计算日收益 (Daily Profit)
        # 逻辑：当前总资产 - 上一个交易日收盘时的总资产
        last_perf = DailyPerformance.objects.filter(
            user=self.user,
            date__lt=current_time.date()  # 找今天之前的记录
        ).order_by('-date').first()

        if last_perf:
            # 日收益 = 当前动态总资产 - 昨收总资产
            self.daily_profit = self.last_total_assets - last_perf.total_assets
        else:
            # 如果没有历史记录（例如第一天交易），日收益 = 总收益
            self.daily_profit = self.total_profit

        # A股 T+1 逻辑：可取资金通常等于昨日的可用余额。这里回测系统可暂设为 balance
        self.withdrawable_cash = self.balance

        self.save()
        return self


# ================= 2. 用户自选股 =================
class UserFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    stock = models.ForeignKey('stocks.StockBasicInfo', on_delete=models.CASCADE, to_field='code', verbose_name="股票")
    add_time = models.DateTimeField(auto_now_add=True, verbose_name="收藏时间")

    class Meta:
        db_table = 'user_favorite'
        verbose_name = "自选股"
        verbose_name_plural = verbose_name
        unique_together = ('user', 'stock')

    def __str__(self):
        return f"{self.user.username} - {self.stock_id}"