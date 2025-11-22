from django.urls import path

from inventory import views

urlpatterns = [
    path('estoque', views.estoque, name='estoque'),
    path('delete_product_estoque', views.delete_product_estoque,
         name='delete-product-estoque'),
    path('manage_products_estoque', views.manage_products_estoque,
         name='manage_products_estoque-page'),
    path('save_product_estoque', views.save_product_estoque,
         name='save-product-estoque-page'),
    path('upload_estoque', views.upload_estoque, name='upload-estoque-page'),
    path(
        'upload_estoque_xml',
        views.EstoqueXMLUploadView.as_view(),
        name='upload-estoque-xml',
    ),
    path(
        'download_estoque_template',
        views.download_estoque_template,
        name='download-estoque-template',
    ),
]
