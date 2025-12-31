from django.contrib import admin
from .models import StockData, StockBasicInfo  # 修改点 1：在这里加上 StockBasicInfo

@admin.register(StockData)
class StockDataAdmin(admin.ModelAdmin):
    list_display = ('code', 'date', 'open', 'high', 'low', 'close', 'volume')
    list_filter = ('code', 'date')
    search_fields = ('code',)

# 修改点 2：为新表增加后台管理配置
@admin.register(StockBasicInfo)
class StockBasicInfoAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')  # 让后台列表显示代码、名称、行业
    search_fields = ('code', 'name')             # 支持按代码或名称搜索