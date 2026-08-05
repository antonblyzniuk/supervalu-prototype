from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.stores.models import Store
from apps.stores.serializers import StoreSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of the signed-in user."""

    store = StoreSerializer(read_only=True)
    is_manager = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_manager",
            "employee_id",
            "store",
            "phone",
            "is_staff",
            "date_joined",
        )
        read_only_fields = fields


class TeamMemberSerializer(serializers.ModelSerializer):
    """Manager-facing view of a colleague, with the store assignment writable."""

    store = StoreSerializer(read_only=True)
    store_slug = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Store.objects.all(),
        source="store",
        write_only=True,
        required=False,
        allow_null=True,
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "employee_id",
            "phone",
            "store",
            "store_slug",
            "is_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("id", "email", "full_name", "last_login", "date_joined")

    def validate_role(self, value):
        """Only an admin may grant or revoke the admin role."""
        actor = self.context["request"].user
        if actor.role == User.Role.ADMIN:
            return value

        if value == User.Role.ADMIN:
            raise serializers.ValidationError("Only an admin can grant the admin role.")
        if self.instance and self.instance.role == User.Role.ADMIN:
            raise serializers.ValidationError("Only an admin can change an admin's role.")
        return value

    def validate(self, attrs):
        actor = self.context["request"].user
        if self.instance and self.instance.pk == actor.pk:
            if "is_active" in attrs and not attrs["is_active"]:
                raise serializers.ValidationError(
                    {"is_active": "You cannot deactivate your own account."}
                )
            if attrs.get("role") and attrs["role"] != actor.role:
                raise serializers.ValidationError(
                    {"role": "You cannot change your own role."}
                )
        return attrs

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # Django admin access tracks the app role, so they cannot drift apart.
        instance.is_staff = instance.role == User.Role.ADMIN or instance.is_superuser
        instance.save(update_fields=["is_staff"])
        return instance


class TeamMemberCreateSerializer(serializers.ModelSerializer):
    """Onboard a colleague. The manager sets a starting password to hand over."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    store_slug = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Store.objects.all(),
        source="store",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "employee_id",
            "phone",
            "store_slug",
            "password",
        )

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return normalized

    def validate_role(self, value):
        actor = self.context["request"].user
        if value == User.Role.ADMIN and actor.role != User.Role.ADMIN:
            raise serializers.ValidationError("Only an admin can create an admin account.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        return user
