from django.db import models
from django.contrib.auth.models import User

# ================= 1. 用户扩展信息 (钱包/头像等) =================
from django.db import models
from django.contrib.auth.models import User
from django.apps import apps  # 🟢 引入 apps 用于动态获取模型


# ... (上面的代码保持不变) ...


from django.db import models
from django.contrib.auth.models import User
from django.apps import apps


# ... (UserProfile 前面的代码保持不变) ...

class UserProfile(models.Model):
    # ... (字段保持不变) ...
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="关联账户")
    phone = models.CharField(max_length=11, blank=True, null=True, verbose_name="手机号")
    avatar = models.CharField(max_length=300, blank=True, null=True,
                              default='https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
                              verbose_name="头像URL")
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="账户余额")
    initial_capital = models.DecimalField(max_digits=14, decimal_places=2, default=200000.00, verbose_name="初始本金")

    class Meta:
        db_table = 'user_profile'
        verbose_name = "用户详细资料"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} - ¥{self.balance}"

    @property
    def total_assets(self):
        total = float(self.balance)

        # 动态导入
        Position = apps.get_model('trade', 'Position')
        SystemSettings = apps.get_model('trade', 'SystemSettings')
        StockMinuteData = apps.get_model('stocks', 'StockMinuteData')  # 引用了正确的分时模型
        StockData = apps.get_model('stocks', 'StockData')

        positions = Position.objects.filter(user=self.user, volume__gt=0)
        if not positions.exists():
            return total

        settings = SystemSettings.objects.first()
        from django.utils import timezone
        current_time = settings.current_mock_time if settings else timezone.now()

        for pos in positions:
            latest_price = 0.0

            # 🔴 修正点 1：字段名由 time 改为 date
            minute_row = StockMinuteData.objects.filter(
                code=pos.stock_code,
                date__lte=current_time  # 这里原来是 time__lte
            ).order_by('-date').first()  # 这里原来是 -time

            if minute_row:
                latest_price = minute_row.close
            else:
                # 日线数据本身就是 date 字段，这里是对的
                day_row = StockData.objects.filter(
                    code=pos.stock_code,
                    date__lte=current_time.date()
                ).order_by('-date').first()

                if day_row:
                    latest_price = day_row.close
                else:
                    latest_price = pos.avg_price

            market_value = pos.volume * float(latest_price)
            total += market_value

        return total
# ================= 2. 用户自选股 (保持不变) =================
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