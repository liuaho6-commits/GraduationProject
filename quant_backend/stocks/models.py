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


class MarketIndexBasicInfo(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="指数代码")
    name = models.CharField(max_length=50, verbose_name="指数名称")
    market = models.CharField(max_length=10, verbose_name="交易所")

    class Meta:
        db_table = "market_index_basic"
        verbose_name = "大盘指数基本信息"
        verbose_name_plural = verbose_name


class MarketIndexDailyData(models.Model):
    code = models.CharField(max_length=20, verbose_name="指数代码")
    date = models.DateField(verbose_name="交易日期")
    open = models.FloatField(verbose_name="开盘点位")
    high = models.FloatField(verbose_name="最高点位")
    low = models.FloatField(verbose_name="最低点位")
    close = models.FloatField(verbose_name="收盘点位")
    volume = models.BigIntegerField(verbose_name="成交量", default=0)
    amount = models.FloatField(verbose_name="成交额", null=True, blank=True)
    amplitude = models.FloatField(verbose_name="振幅", null=True, blank=True)
    change_pct = models.FloatField(verbose_name="涨跌幅", null=True, blank=True)
    change_amount = models.FloatField(verbose_name="涨跌额", null=True, blank=True)
    turnover_rate = models.FloatField(verbose_name="换手率", null=True, blank=True)
    source = models.CharField(max_length=20, default="akshare", verbose_name="数据源")

    class Meta:
        db_table = "market_index_daily"
        indexes = [models.Index(fields=["code", "date"])]
        constraints = [
            models.UniqueConstraint(fields=["code", "date"], name="uniq_market_index_daily")
        ]
        verbose_name = "大盘指数日线数据"
        verbose_name_plural = verbose_name


class MarketIndexMinuteData(models.Model):
    code = models.CharField(max_length=20, verbose_name="指数代码")
    date = models.DateTimeField(verbose_name="交易时间")
    open = models.FloatField(verbose_name="开盘点位")
    high = models.FloatField(verbose_name="最高点位")
    low = models.FloatField(verbose_name="最低点位")
    close = models.FloatField(verbose_name="收盘点位")
    volume = models.BigIntegerField(verbose_name="成交量", default=0)
    amount = models.FloatField(verbose_name="成交额", null=True, blank=True)
    source = models.CharField(max_length=20, default="pytdx", verbose_name="数据源")

    class Meta:
        db_table = "market_index_minute"
        indexes = [models.Index(fields=["code", "date"])]
        constraints = [
            models.UniqueConstraint(fields=["code", "date"], name="uniq_market_index_minute")
        ]
        verbose_name = "大盘指数5分钟数据"
        verbose_name_plural = verbose_name
