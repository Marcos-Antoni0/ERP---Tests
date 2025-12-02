from django.urls import path

from tables import views

urlpatterns = [
    path('mesas/', views.mesas, name='mesas'),
    path('mesas/salvar/', views.salvar_mesa, name='salvar_mesa'),
    path('mesas/<int:table_id>/salvar/',
         views.salvar_mesa, name='atualizar_mesa'),
    path('mesas/<int:table_id>/excluir/',
         views.excluir_mesa, name='excluir_mesa'),
    path('mesas/<int:table_id>/detalhes/',
         views.mesa_detalhe, name='mesa-detalhe'),
    path('mesas/<int:table_id>/abrir-comanda/',
         views.abrir_comanda, name='abrir_comanda'),
    path('mesas/comanda/<int:order_id>/atualizar/',
         views.atualizar_comanda, name='atualizar_comanda'),
    path('mesas/comanda/<int:order_id>/fechar/',
         views.fechar_comanda, name='fechar_comanda'),
    path('mesas/comanda/<int:order_id>/reabrir/',
         views.reabrir_comanda, name='reabrir_comanda'),
    path('mesas/comanda/<int:order_id>/excluir/',
         views.excluir_comanda, name='excluir_comanda'),
    path('mesas/comanda/<int:order_id>/item/',
         views.adicionar_item_comanda, name='adicionar_item_comanda'),
    path(
        'mesas/comanda/item/<int:item_id>/atualizar/',
        views.atualizar_item_comanda,
        name='atualizar_item_comanda',
    ),
    path(
        'mesas/comanda/item/<int:item_id>/remover/',
        views.remover_item_comanda,
        name='remover_item_comanda',
    ),
    path(
        'mesas/produto/<int:product_id>/alternar/',
        views.toggle_product_availability,
        name='toggle_product_availability',
    ),
]
