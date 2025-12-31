from django.contrib import admin
from .models import Strategy, Position, Order, TradeRecord, SystemSettings, DailyPerformance, IntradayPerformance

@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'create_time')

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock_code', 'volume', 'avg_price')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock_code', 'direction', 'price', 'volume', 'status', 'order_time')

@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    list_display = ('order', 'stock_code', 'price', 'volume', 'amount', 'trade_time')

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('time_speed', 'current_mock_time', 'skip_non_trading')

@admin.register(DailyPerformance)
class DailyPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'total_assets', 'day_profit', 'total_return_rate')

@admin.register(IntradayPerformance)
class IntradayPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'time', 'total_assets', 'total_return_rate')