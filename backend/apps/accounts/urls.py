from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .auth_serializers import EmailTokenObtainPairView
from .views import AdminBootstrapView, MeView, TeamViewSet

app_name = "accounts"

router = DefaultRouter()
router.register("team", TeamViewSet, basename="team")

urlpatterns = [
    path("token/", EmailTokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token-verify"),
    path("me/", MeView.as_view(), name="me"),
    path("bootstrap-admin/", AdminBootstrapView.as_view(), name="bootstrap-admin"),
    path("", include(router.urls)),
]
