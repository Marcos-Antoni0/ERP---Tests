from django.urls import path

from core import views

urlpatterns = [
    path('', views.home, name='home-page'),
    path('configuracoes/', views.ConfiguracoesView.as_view(),
         name='configuracoes-page'),
    path('about/', views.about, name='about-redirect'),
]
