from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    CurrentUserView,
    DeviceRegistrationCreateView,
    DeviceRegistrationDeleteView,
    RegisterView,
    SavedRecipientDetailView,
    SavedRecipientListCreateView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", TokenObtainPairView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path(
        "devices/",
        DeviceRegistrationCreateView.as_view(),
        name="device-registration",
    ),
    path(
        "devices/<uuid:pk>/",
        DeviceRegistrationDeleteView.as_view(),
        name="device-registration-delete",
    ),
    path(
        "recipients/",
        SavedRecipientListCreateView.as_view(),
        name="saved-recipients",
    ),
    path(
        "recipients/<uuid:pk>/",
        SavedRecipientDetailView.as_view(),
        name="saved-recipient",
    ),
]
