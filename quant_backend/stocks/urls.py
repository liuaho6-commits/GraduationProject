from django.urls import path
from . import views

urlpatterns = [
    # K线数据接口
    path('api/data/<str:stock_code>/', views.get_stock_data_api, name='get_data'),

    # 行情列表接口
    path('api/market/', views.get_market_list_api, name='get_market_list'),
]