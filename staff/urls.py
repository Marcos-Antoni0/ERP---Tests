from django.urls import path

from staff import views

urlpatterns = [
    path('garcons/', views.garcons, name='garcons'),
    path('garcons/salvar/', views.salvar_garcom, name='salvar_garcom'),
    path('garcons/<int:garcom_id>/salvar/',
         views.salvar_garcom, name='editar_garcom'),
    path('garcons/<int:garcom_id>/excluir/',
         views.excluir_garcom, name='excluir_garcom'),
]
