from django.urls import path

from catalog import views

urlpatterns = [
    path("category", views.category, name="category-page"),
    path("manage_category", views.manage_category, name="manage_category-page"),
    path("save_category", views.save_category, name="save-category-page"),
    path("delete_category", views.delete_category, name="delete-category"),
    path("upload_categories", views.upload_categories, name="upload-categories-page"),
    path(
        "download_category_template",
        views.download_category_template,
        name="download-category-template",
    ),
    path("upload_products", views.upload_products, name="upload-products-page"),
    path(
        "download_product_template",
        views.download_product_template,
        name="download-product-template",
    ),
    path("products", views.products, name="product-page"),
    path("manage_products", views.manage_products, name="manage_products-page"),
    path("test", views.test, name="test-page"),
    path("save_product", views.save_product, name="save-product-page"),
    path("delete_product", views.delete_product, name="delete-product"),
]