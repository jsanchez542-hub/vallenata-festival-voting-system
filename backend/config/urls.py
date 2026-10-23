from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Votaciones del Festival"
admin.site.site_title = "Votaciones del Festival"
admin.site.index_title = "Administración"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("festival.urls")),
]
