from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views

urlpatterns = [
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='accounts/login.html', redirect_authenticated_user=True
        ),
        name='login',
    ),
    path('userlogin', views.login_user, name='login-user'),
    path('logout', views.logout_user, name='logout'),
]
