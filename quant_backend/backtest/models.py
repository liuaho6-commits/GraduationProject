from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Factor(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="因子名称")
    code = models.CharField(max_length=100, unique=True, verbose_name="因子代码")
    description = models.TextField(blank=True, null=True, verbose_name="因子描述")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")

    class Meta:
        db_table = 'backtest_factor'
        verbose_name = "量化因子"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.code})"


class BacktestTask(models.Model):
    STATUS_CHOICES = (
        ('pending', '等待中'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="所属用户")
    task_name = models.CharField(max_length=200, verbose_name="回测任务名称")
    start_date = models.DateField(verbose_name="回测开始日期")
    end_date = models.DateField(verbose_name="回测结束日期")
    initial_capital = models.DecimalField(max_digits=15, decimal_places=2, default=100000.00, verbose_name="初始资金")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="任务状态")

    # JSON 存储选择的因子和权重，例如：{"PE": 0.3, "PB": 0.3, "MOM": 0.4}
    factor_weights = models.JSONField(verbose_name="因子权重配置", default=dict)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    error_message = models.TextField(blank=True, null=True, verbose_name="错误信息")

    class Meta:
        db_table = 'backtest_task'
        verbose_name = "回测任务"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.task_name


class BacktestResult(models.Model):
    task = models.OneToOneField(BacktestTask, on_delete=models.CASCADE, related_name='result', verbose_name="关联任务")
    annualized_return = models.FloatField(null=True, blank=True, verbose_name="年化收益率")
    max_drawdown = models.FloatField(null=True, blank=True, verbose_name="最大回撤")
    sharpe_ratio = models.FloatField(null=True, blank=True, verbose_name="夏普比率")
    win_rate = models.FloatField(null=True, blank=True, verbose_name="胜率")

    # JSON 存储资金曲线、每日收益等，便于前端直接读取绘图
    equity_curve = models.JSONField(verbose_name="资金曲线", default=list)
    positions_history = models.JSONField(verbose_name="持仓历史", default=list)

    class Meta:
        db_table = 'backtest_result'
        verbose_name = "回测结果"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"Result for {self.task.task_name}"