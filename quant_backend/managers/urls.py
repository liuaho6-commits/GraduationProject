from django.urls import path
from .views import AdminLoginView, DashboardStatsView, UserListView

urlpatterns = [
    path('login/', AdminLoginView.as_view(), name='admin_login'),
    path('dashboard/', DashboardStatsView.as_view(), name='admin_dashboard'),
    path('users/', UserListView.as_view(), name='admin_user_list'),
]