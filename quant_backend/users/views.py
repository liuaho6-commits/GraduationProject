from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .models import UserProfile, UserFavorite
from .serializers import UserProfileSerializer, UserSerializer, RegisterSerializer, UserFavoriteSerializer
from stocks.models import StockBasicInfo
from django.utils import timezone


# ================= 登录视图 =================
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response({'code': 400, 'msg': '请输入用户名和密码'})
        user = authenticate(username=username, password=password)
        if user is not None:
            if not user.is_active:
                return Response({'code': 403, 'msg': '账户已被禁用'})
            token, created = Token.objects.get_or_create(user=user)
            return Response({'code': 200, 'msg': '登录成功', 'data': {'token': token.key, 'username': user.username}})
        else:
            return Response({'code': 400, 'msg': '用户名或密码错误'})


# ================= 用户信息视图 (优化加载速度) =================
# quant_backend/users/views.py

# ... (其他 import)

class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        # 实时触发一次高性能刷新
        profile.update_asset_cache()

        return Response({
            'code': 200,
            'data': {
                'total_assets': float(profile.last_total_assets),
                'market_value': float(profile.last_market_value),
                'balance': float(profile.balance),
                'withdrawable': float(profile.withdrawable_cash),
                'daily_profit': float(profile.daily_profit),
                'total_profit': float(profile.total_profit),
                # 👇👇👇 必须加上这一行 👇👇👇
                'initial_capital': float(profile.initial_capital),
                'username': request.user.username
            }
        })
# ================= 注册视图 =================
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'code': 200, 'msg': '注册成功'})
        errors = [f"{msg[0]}" for field, msg in serializer.errors.items()]
        return Response({'code': 400, 'msg': errors[0] if errors else '注册失败'})


# ================= 自选股视图 =================
class UserFavoriteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        favorites = UserFavorite.objects.filter(user=request.user).order_by('-add_time')
        return Response({'code': 200, 'data': UserFavoriteSerializer(favorites, many=True).data})

    def post(self, request):
        code = request.data.get('code')
        if not code: return Response({'code': 400, 'msg': '代码为空'})
        stock = StockBasicInfo.objects.filter(code=code).first()
        if not stock: return Response({'code': 404, 'msg': '股票不存在'})
        if UserFavorite.objects.filter(user=request.user, stock=stock).exists():
            return Response({'code': 400, 'msg': '已存在'})
        UserFavorite.objects.create(user=request.user, stock=stock)
        return Response({'code': 200, 'msg': '添加成功'})

    def delete(self, request):
        code = request.data.get('code') or request.query_params.get('code')
        if not code: return Response({'code': 400, 'msg': '参数缺失'})
        deleted, _ = UserFavorite.objects.filter(user=request.user, stock__code=code).delete()
        return Response({'code': 200, 'msg': '删除成功'}) if deleted else Response({'code': 400, 'msg': '未找到'})