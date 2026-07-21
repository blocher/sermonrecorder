from django.urls import path
from rest_framework.routers import SimpleRouter

from .private_audio import sermon_private_audio
from .views import SermonViewSet

router = SimpleRouter()
router.register("", SermonViewSet, basename="sermon")

urlpatterns = [
    path(
        "<uuid:sermon_id>/audio/",
        sermon_private_audio,
        name="sermon-private-audio",
    ),
    *router.urls,
]
