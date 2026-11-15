from django.urls import path

from . import views


urlpatterns = [
    path("<slug:module>/", views.module_list, name="module_list"),
    path("<slug:module>/new/", views.module_create, name="module_create"),
    path("<slug:module>/<int:pk>/", views.module_detail, name="module_detail"),
    path("<slug:module>/<int:pk>/edit/", views.module_update, name="module_update"),
    path("<slug:module>/<int:pk>/delete/", views.module_delete, name="module_delete"),
]
