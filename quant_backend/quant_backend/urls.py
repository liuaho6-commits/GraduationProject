from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🟢 路由方案 A: 匹配 /trade/api/...
    path('trade/api/', include('trade.urls')),

    # 🟢 路由方案 B: 匹配 /api/trade/... (增加兼容性)
    path('api/trade/', include('trade.urls')),

    # 🟢 用户模块双重匹配
    path('users/api/', include('users.urls')),
    path('api/users/', include('users.urls')),

    path('stocks/', include('stocks.urls')),
]