from rest_framework.routers import DefaultRouter

from .views import DocketViewSet

app_name = "dockets"

router = DefaultRouter()
router.register("", DocketViewSet, basename="docket")

urlpatterns = router.urls
