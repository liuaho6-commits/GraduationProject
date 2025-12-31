from rest_framework import serializers
from .models import StockData, StockMinuteData, StockBasicInfo

class StockDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockData
        fields = '__all__'

# 🟢 新增分钟数据序列化器
class StockMinuteDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMinuteData
        fields = '__all__'