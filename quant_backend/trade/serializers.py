from rest_framework import serializers
from .models import Strategy, Order, Position, DailyPerformance, IntradayPerformance
from stocks.models import StockBasicInfo  # 🟢 引入股票信息模型

class StrategySerializer(serializers.ModelSerializer):
    class Meta:
        model = Strategy
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    # 🟢 新增：获取股票名称
    stock_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'

    def get_stock_name(self, obj):
        # 尝试查询股票名称，查不到就返回 code
        stock = StockBasicInfo.objects.filter(code=obj.stock_code).first()
        return stock.name if stock else obj.stock_code

class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = '__all__'

class DailyPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyPerformance
        fields = '__all__'

class IntradayPerformanceSerializer(serializers.ModelSerializer):
    time = serializers.DateTimeField(format="%H:%M")
    class Meta:
        model = IntradayPerformance
        fields = '__all__'