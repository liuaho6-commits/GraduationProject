from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, UserFavorite
from stocks.models import StockBasicInfo, StockData, StockMinuteData
from trade.time_utils import get_mock_now  # 🟢 引入和全市场一样的获取时间函数
from django.utils import timezone
import datetime


# ================= 用户相关序列化器 (保持不变) =================

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'balance', 'initial_capital', 'phone', 'avatar']


class UserSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(source='profile.balance', max_digits=14, decimal_places=2, read_only=True)
    total_assets = serializers.DecimalField(source='profile.balance', max_digits=14, decimal_places=2, read_only=True)
    initial_capital = serializers.DecimalField(source='profile.initial_capital', max_digits=14, decimal_places=2,
                                               read_only=True)
    avatar = serializers.CharField(source='profile.avatar', read_only=True)
    phone = serializers.CharField(source='profile.phone', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'balance', 'initial_capital', 'total_assets', 'avatar', 'phone')


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
        UserProfile.objects.create(
            user=user,
            balance=200000.00,
            initial_capital=200000.00,
            phone=phone
        )
        return user


# ================= 自选股序列化器 (核心修改) =================

class UserFavoriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='stock.name', read_only=True)
    price = serializers.SerializerMethodField()
    change = serializers.SerializerMethodField()

    class Meta:
        model = UserFavorite
        fields = ('id', 'stock', 'name', 'add_time', 'price', 'change')

    def _get_market_snapshot(self, stock_code):
        """
        [内部辅助函数]
        完全复刻 get_market_list_api 的逻辑来获取当前价格和昨收。
        返回: (current_price, prev_close)
        """
        # 1. 获取上帝时间并转为 Naive Time
        mock_now = get_mock_now()
        if timezone.is_aware(mock_now):
            mock_naive = timezone.make_naive(mock_now)
        else:
            mock_naive = mock_now

        # 2. 尝试获取最新的分时数据
        # 宽容查找：查mock_now之后1天内的数据，防止边界丢失
        candidates = StockMinuteData.objects.filter(
            code=stock_code,
            date__lte=mock_now + datetime.timedelta(days=1)
        ).order_by('-date')[:50]

        last_min = None
        # 内存过滤：找到第一个时间 <= mock_naive 的数据
        for cand in candidates:
            cand_naive = timezone.make_naive(cand.date) if timezone.is_aware(cand.date) else cand.date
            if cand_naive <= mock_naive:
                last_min = cand
                break

        price = 0.0
        prev_close = 0.0

        if last_min:
            # === 命中分时数据 ===
            price = last_min.close
            # 找该分时日期之前的最近一条日线作为昨收
            prev_day_orig = StockData.objects.filter(
                code=stock_code,
                date__lt=last_min.date.date()
            ).order_by('-date').first()

            if prev_day_orig:
                prev_close = prev_day_orig.close
        else:
            # === 未命中分时数据，尝试兜底日线数据 ===
            # 例如：周末、还未开盘、或分时数据确实缺失
            mock_today = mock_naive.date()
            last_day = StockData.objects.filter(
                code=stock_code,
                date__lte=mock_today
            ).order_by('-date').first()

            if last_day:
                price = last_day.close
                # 找该日线日期之前的最近一条日线作为昨收
                prev_day = StockData.objects.filter(
                    code=stock_code,
                    date__lt=last_day.date
                ).order_by('-date').first()
                if prev_day:
                    prev_close = prev_day.close

        return price, prev_close

    def get_price(self, obj):
        price, _ = self._get_market_snapshot(obj.stock.code)
        return price

    def get_change(self, obj):
        price, prev_close = self._get_market_snapshot(obj.stock.code)
        if price and prev_close and prev_close > 0:
            return round((price - prev_close) / prev_close * 100, 2)
        return 0.0