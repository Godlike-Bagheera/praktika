"""forum URL Configuration."""
from django.contrib import admin
from django.urls import include, path

from forumapp.views import health_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health_view, name="health"),
    path("api/", include("forumapp.api_urls")),
]
