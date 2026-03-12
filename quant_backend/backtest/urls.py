from django.urls import path
from .views import RunBacktestView

urlpatterns = [
    path('run/', RunBacktestView.as_view(), name='run_backtest'),
]