from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, StoreDepartmentViewSet

app_name = "departments"

router = DefaultRouter()
# Registered before the bare prefix so "in-stores" is not read as a slug.
router.register("in-stores", StoreDepartmentViewSet, basename="store-department")
router.register("", DepartmentViewSet, basename="department")

urlpatterns = [path("", include(router.urls))]
