from django.urls import path

from sales import views
from tables.views import reabrir_venda_mesa

urlpatterns = [
    path('caixa/', views.cashier_dashboard, name='cashier'),
    path('caixa/abrir/', views.open_cash_session, name='open_cash_session'),
    path('caixa/movimentacao/', views.register_cash_movement,
         name='register_cash_movement'),
    path('caixa/fechar/', views.close_cash_session, name='close_cash_session'),
    path('caixa/relatorio/<int:session_id>/',
         views.cashier_session_report, name='cashier_session_report'),
    path('pos', views.pos, name='pos-page'),
    path('checkout-modal', views.checkout_modal, name='checkout-modal'),
    path('save-pos', views.save_pos, name='save-pos'),
    path('sales', views.salesList, name='sales-page'),
    path('sales/<int:sale_id>/reabrir-comanda/',
         reabrir_venda_mesa, name='reabrir_venda_mesa'),
    path('receipt', views.receipt, name='receipt-modal'),
    path('delete_sale', views.delete_sale, name='delete-sale'),
    path('salesreport', views.sales_report, name='sales_report'),
    path('sales-report/export/', views.export_sales_report,
         name='export_sales_report'),
]
