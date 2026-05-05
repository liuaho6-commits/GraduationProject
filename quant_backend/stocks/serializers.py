from rest_framework import serializers
from .models import (
    MarketIndexDailyData,
    MarketIndexMinuteData,
    StockData,
    StockMinuteData,
)

class StockDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockData
        fields = '__all__'

# 🟢 新增分钟数据序列化器
class StockMinuteDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMinuteData
        fields = '__all__'


class MarketIndexDailyDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketIndexDailyData
        fields = '__all__'


class MarketIndexMinuteDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketIndexMinuteData
        fields = '__all__'
