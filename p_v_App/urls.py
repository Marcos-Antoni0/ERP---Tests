from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path('redirect-admin', RedirectView.as_view(url='/admin'), name='redirect-admin'),
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('catalog.urls')),
    path('', include('sales.urls')),
    path('', include('orders.urls')),
    path('', include('inventory.urls')),
    path('', include('tables.urls')),
    path('', include('staff.urls')),
    path('', include('clients.urls')),
    path('', include('debts.urls')),
]
