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


# ================= 用户信息视图 (修复 unpack 错误) =================
class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user, balance=200000, initial_capital=200000)

        real_balance = profile.balance

        try:
            from trade.views import calculate_asset_status
            from trade.time_utils import get_mock_now

            now = get_mock_now()
            if timezone.is_naive(now): now = timezone.make_aware(now)

            # 🟢 修复：接收 4 个返回值 (忽略最后一个成本字段)
            _, _, calculated_cash, _ = calculate_asset_status(user, now)

            real_balance = calculated_cash

        except Exception as e:
            # 这里的报错已经被修复，应该不会再打印了
            print(f"❌ [UserInfo] 余额计算失败: {e}")

        serializer = UserProfileSerializer(profile)
        data = serializer.data
        data['balance'] = float(real_balance)
        data['total_assets'] = float(real_balance)

        return Response({'code': 200, 'msg': '获取成功', 'data': data})


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