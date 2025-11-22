from django.urls import path

from orders import views

urlpatterns = [
    path('pedidos/', views.pedidos, name='pedidos'),
    path('pedidos/atualizar-status/<int:id>/',
         views.atualizar_status_pedido, name='atualizar_status_pedido'),
    path('finalizar_pedido/<int:pedido_id>/',
         views.finalizar_pedido, name='finalizar_pedido'),
    path('delete_pedido', views.delete_pedido, name='delete_pedido'),
    path('detalhe_pedido', views.view_pedido, name='view-pedido'),
]
