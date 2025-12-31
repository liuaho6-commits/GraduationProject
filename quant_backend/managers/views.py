from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

# 引入我们刚才写的权限
from .permissions import IsSuperUser
# 引入其他 App 的模型用于统计
from stocks.models import StockBasicInfo, StockData
from users.models import UserProfile


# ================= 1. 管理员专属登录 =================
class AdminLoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)

        # 关键逻辑：不仅要密码对，还得是管理员(is_staff 或 is_superuser)
        if user is not None and user.is_superuser:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                "code": 200,
                "msg": "管理员登录成功",
                "token": token.key,
                "username": user.username,
                "role": "admin"
            })
        elif user is not None:
            return Response({"code": 403, "msg": "您不是管理员，无法登录后台"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"code": 401, "msg": "账号或密码错误"}, status=status.HTTP_401_UNAUTHORIZED)


# ================= 2. 系统仪表盘统计 (Dashboard) =================
class DashboardStatsView(APIView):
    # 只有带了 Token 且是超级管理员才能看
    permission_classes = [IsSuperUser]

    def get(self, request):
        user_count = User.objects.count()
        stock_count = StockBasicInfo.objects.count()
        data_count = StockData.objects.count()

        # 计算总资金池 (所有用户的模拟资金之和)
        total_balance = 0
        profiles = UserProfile.objects.all()
        for p in profiles:
            total_balance += p.balance

        return Response({
            "code": 200,
            "data": {
                "total_users": user_count,  # 总用户数
                "total_stocks": stock_count,  # 股票数量
                "total_records": data_count,  # 行情数据量
                "market_capital": total_balance  # 模拟盘总资金
            }
        })


# ================= 3. 用户列表管理 =================
class UserListView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        # 获取所有用户 (排除管理员自己)
        users = User.objects.filter(is_superuser=False).order_by('-date_joined')

        user_list = []
        for u in users:
            # 兼容处理：防止部分老用户没有 profile
            phone = u.profile.phone if hasattr(u, 'profile') else "无"
            balance = u.profile.balance if hasattr(u, 'profile') else 0

            user_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "phone": phone,
                "balance": balance,
                "date_joined": u.date_joined.strftime("%Y-%m-%d %H:%M")
            })

        return Response({
            "code": 200,
            "data": user_list
        })