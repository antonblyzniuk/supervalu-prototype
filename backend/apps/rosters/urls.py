from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ShiftViewSet, roster_board, roster_export

app_name = "rosters"

router = DefaultRouter()
router.register("shifts", ShiftViewSet, basename="shift")

urlpatterns = [
    path("board/", roster_board, name="board"),
    path("export/", roster_export, name="export"),
    path("", include(router.urls)),
]
