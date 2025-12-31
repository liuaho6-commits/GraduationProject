from django.db import models

# 1. 日线数据 (用于计算涨跌幅、展示日K线)
class StockData(models.Model):
    code = models.CharField(max_length=20, verbose_name="股票代码")
    date = models.DateField(verbose_name="交易日期")  # 🟢 只有日期
    open = models.FloatField(verbose_name="开盘价")
    high = models.FloatField(verbose_name="最高价")
    low = models.FloatField(verbose_name="最低价")
    close = models.FloatField(verbose_name="收盘价")
    volume = models.BigIntegerField(verbose_name="成交量")
    amount = models.FloatField(verbose_name="成交额")

    class Meta:
        db_table = 'stock_data_daily'  # 改个清晰的表名
        indexes = [models.Index(fields=['code', 'date'])]
        verbose_name = "日线数据"
        verbose_name_plural = verbose_name

# 2. 分钟数据 (用于回测交易、展示分时图)
class StockMinuteData(models.Model):
    code = models.CharField(max_length=20, verbose_name="股票代码")
    date = models.DateTimeField(verbose_name="交易时间") # 🟢 带时间
    open = models.FloatField(verbose_name="开盘价")
    high = models.FloatField(verbose_name="最高价")
    low = models.FloatField(verbose_name="最低价")
    close = models.FloatField(verbose_name="收盘价")
    volume = models.BigIntegerField(verbose_name="成交量")
    amount = models.FloatField(verbose_name="成交额")

    class Meta:
        db_table = 'stock_data_minute'
        indexes = [models.Index(fields=['code', 'date'])]
        verbose_name = "分钟数据"
        verbose_name_plural = verbose_name

class StockBasicInfo(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="股票代码")
    name = models.CharField(max_length=50, verbose_name="股票名称")

    class Meta:
        verbose_name = "股票基本信息"
        verbose_name_plural = verbose_name