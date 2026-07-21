from django.urls import path
from rest_framework.routers import SimpleRouter

from .editing_views import (
    ReflectionDetailView,
    ReflectionListCreateView,
    StudyArtifactDetailView,
)
from .emailing import SermonEmailView
from .private_audio import sermon_private_audio
from .sharing import SermonShareLinkView
from .views import SermonViewSet

router = SimpleRouter()
router.register("", SermonViewSet, basename="sermon")

urlpatterns = [
    path(
        "<uuid:sermon_id>/email/",
        SermonEmailView.as_view(),
        name="sermon-email",
    ),
    path(
        "<uuid:sermon_id>/share/",
        SermonShareLinkView.as_view(),
        name="sermon-share-link",
    ),
    path(
        "<uuid:sermon_id>/artifacts/<str:kind>/",
        StudyArtifactDetailView.as_view(),
        name="sermon-study-artifact",
    ),
    path(
        "<uuid:sermon_id>/reflections/",
        ReflectionListCreateView.as_view(),
        name="sermon-reflections",
    ),
    path(
        "<uuid:sermon_id>/reflections/<uuid:reflection_id>/",
        ReflectionDetailView.as_view(),
        name="sermon-reflection",
    ),
    path(
        "<uuid:sermon_id>/audio/",
        sermon_private_audio,
        name="sermon-private-audio",
    ),
    *router.urls,
]
