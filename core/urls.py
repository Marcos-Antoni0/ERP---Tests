from django.urls import path

from core import views

urlpatterns = [
    path("", views.home, name="home-page"),
    path("about/", views.about, name="about-page"),
]
