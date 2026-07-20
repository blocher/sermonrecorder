from rest_framework.routers import SimpleRouter

from .views import SermonViewSet

router = SimpleRouter()
router.register("", SermonViewSet, basename="sermon")

urlpatterns = router.urls
