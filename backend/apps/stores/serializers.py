from rest_framework import serializers

from .models import Store


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ("id", "code", "slug", "name", "is_active")
        read_only_fields = fields
