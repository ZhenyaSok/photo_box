from django.urls import path

from . import views

urlpatterns = [
    path(
        "notifications/",
        views.NotificationViewSet.as_view({"post": "create"}),
        name="notifications",
    ),
]
