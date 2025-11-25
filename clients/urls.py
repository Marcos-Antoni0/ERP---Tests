from django.urls import path

from clients.views import ClientListView

urlpatterns = [
    path('clients/', ClientListView.as_view(), name='clients-list'),
]
