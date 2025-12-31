from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, UserFavorite
from stocks.models import StockBasicInfo, StockData

# 🟢 补全缺失的：用户资料序列化器
class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'balance', 'initial_capital', 'phone', 'avatar']

# 用户主序列化器 (用于嵌套显示)
class UserSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(source='profile.balance', max_digits=14, decimal_places=2, read_only=True)
    total_assets = serializers.DecimalField(source='profile.balance', max_digits=14, decimal_places=2, read_only=True) # 暂时用balance代替，实际由视图层覆盖
    initial_capital = serializers.DecimalField(source='profile.initial_capital', max_digits=14, decimal_places=2, read_only=True)
    avatar = serializers.CharField(source='profile.avatar', read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'balance', 'initial_capital', 'total_assets', 'avatar', 'phone')

# 注册序列化器
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=True)
    phone = serializers.CharField(write_only=True, required=True, min_length=11, max_length=11)

    class Meta:
        model = User
        fields = ('username', 'password', 'password_confirm', 'phone')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "两次输入的密码不一致"})
        if User.objects.filter(username=attrs['username']).exists():
            raise serializers.ValidationError({"username": "该用户名已存在"})
        return attrs

    def create(self, validated_data):
        phone = validated_data.get('phone')
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        # 创建资料时，默认本金和余额一致，防止刚注册就收益率爆炸
        UserProfile.objects.create(
            user=user,
            balance=200000.00,
            initial_capital=200000.00,
            phone=phone
        )
        return user

# 自选股序列化器
class UserFavoriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='stock.name', read_only=True)
    price = serializers.SerializerMethodField()

    class Meta:
        model = UserFavorite
        fields = ('id', 'stock', 'name', 'add_time', 'price')

    def get_price(self, obj):
        # 尝试获取最新价格
        last_row = StockData.objects.filter(code=obj.stock.code).order_by('-date').first()
        return last_row.close if last_row else 0.0