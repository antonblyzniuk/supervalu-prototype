from rest_framework import viewsets

from .models import Store
from .serializers import StoreSerializer


class StoreViewSet(viewsets.ReadOnlyModelViewSet):
    """Stores are reference data — seeded by migration, managed in the admin."""

    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer
    pagination_class = None
    lookup_field = "slug"
