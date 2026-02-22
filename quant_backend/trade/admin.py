from django.contrib import admin
from django.contrib import messages  # <--- 修复了这里的报错
from .models import (
    Strategy, Position, Order, TradeRecord,
    SystemSettings, DailyPerformance, IntradayPerformance,
    TimeFlowSettings, TimeResetSettings
)


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


@admin.register(DailyPerformance)
class DailyPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'total_assets', 'day_profit', 'total_return_rate')


@admin.register(IntradayPerformance)
class IntradayPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'time', 'total_assets', 'total_return_rate')


# ================= 1. 流速控制页面 (普通保存) =================
@admin.register(TimeFlowSettings)
class TimeFlowSettingsAdmin(admin.ModelAdmin):
    # 只显示流速相关字段
    fields = ('time_speed', 'skip_non_trading')
    list_display = ('time_speed', 'skip_non_trading', 'current_mock_time')

    def has_add_permission(self, request):
        # 禁止创建多条记录，始终只允许修改现有的
        return False if SystemSettings.objects.exists() else True

    def has_delete_permission(self, request, obj=None):
        return False


# ================= 2. 时间穿越页面 (保存即重置) =================
@admin.register(TimeResetSettings)
class TimeResetSettingsAdmin(admin.ModelAdmin):
    # 只显示时间字段
    fields = ('current_mock_time',)
    list_display = ('current_mock_time', 'time_speed')

    # 🔴 核心逻辑：重写保存方法
    def save_model(self, request, obj, form, change):
        # 1. 先保存时间修改
        super().save_model(request, obj, form, change)

        # 2. 这里的 obj 其实就是 SystemSettings 的实例
        # 直接调用你在 models.py 里写好的核弹重置方法
        obj.hard_reset_world()

        # 3. 给管理员弹个窗提示 (现在 messages 已正确导入)
        messages.set_level(request, messages.WARNING)
        messages.warning(request, f"🚀 穿越成功！时间已跃迁至 {obj.current_mock_time}，所有持仓和资金已重置！")

    def has_add_permission(self, request):
        return False if SystemSettings.objects.exists() else True

    def has_delete_permission(self, request, obj=None):
        return False


# 注销原始入口，避免混淆
#admin.site.unregister(SystemSettings)