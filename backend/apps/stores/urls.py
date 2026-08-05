from rest_framework.routers import DefaultRouter

from .views import StoreViewSet

app_name = "stores"

router = DefaultRouter()
router.register("", StoreViewSet, basename="store")

urlpatterns = router.urls
