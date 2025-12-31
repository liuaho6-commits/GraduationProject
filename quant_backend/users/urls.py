from django.urls import path
from .views import LoginView, UserInfoView, RegisterView, UserFavoriteView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('info/', UserInfoView.as_view(), name='user_info'),
    path('register/', RegisterView.as_view(), name='register'),
    path('favorites/', UserFavoriteView.as_view(), name='favorites'),
]