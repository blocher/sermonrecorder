from django.urls import path

from .sharing import PublicSharedSermonView, shared_sermon_audio

urlpatterns = [
    path(
        "<str:token>/audio/",
        shared_sermon_audio,
        name="shared-sermon-audio",
    ),
    path(
        "<str:token>/",
        PublicSharedSermonView.as_view(),
        name="shared-sermon",
    ),
]
