from django.urls import path

from debts.views import DebtDeleteView, DebtListView, DebtPayView

urlpatterns = [
    path('debts/', DebtListView.as_view(), name='debts-list'),
    path('debts/<int:debt_id>/pay/', DebtPayView.as_view(), name='debt-pay'),
    path('debts/<int:debt_id>/delete/', DebtDeleteView.as_view(), name='debt-delete'),
]
