from django.urls import path
from .views import (
    FundTransferView,
    StrategyView,
    PerformanceView,
    OrderListView,
    PlaceOrderView,
    PositionDetailView,
    SystemTimeView,
    PositionListView,
    SystemControlView# 🟢 记得引入
)

urlpatterns = [
    path('performance/', PerformanceView.as_view(), name='performance'),
    path('transfer/', FundTransferView.as_view(), name='transfer'),
    path('strategy/', StrategyView.as_view(), name='strategy'),

    # 🟢 新增持仓列表接口
    path('positions/', PositionListView.as_view(), name='positions'),

    path('orders/', OrderListView.as_view(), name='orders'),
    path('place_order/', PlaceOrderView.as_view(), name='place_order'),
    path('position/<str:stock_code>/', PositionDetailView.as_view(), name='position_detail'),
    path('time/', SystemTimeView.as_view(), name='system_time'),
    path('control/', SystemControlView.as_view(), name='system_control'),

    path('time/', SystemTimeView.as_view(), name='system_time'),
]