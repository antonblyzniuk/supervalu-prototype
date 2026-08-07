import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.departments.models import StoreDepartment
from apps.departments.serializers import StoreDepartmentLabelSerializer
from apps.stores.models import Store
from apps.stores.serializers import StoreSerializer

from .models import User


def department_field(**kwargs):
    """Writable department reference, keyed by slug like `store_slug`.

    Points at a branch of a department ("Deli · Balbriggan"), so it carries the
    store with it — see `validate_store_matches_department`. A branch exists
    only where the store actually runs the department, so the queryset needs no
    filter beyond the kind still being live. `allow_null` stays off: every
    colleague belongs to a department, so there is no "unassign" here. Accounts
    that predate departments — and the bootstrap admin — read back as null until
    someone picks one.
    """
    return serializers.SlugRelatedField(
        slug_field="slug",
        queryset=StoreDepartment.objects.filter(department__is_active=True),
        source="department",
        **kwargs,
    )


def hourly_rate_field(**kwargs):
    """What we pay someone per hour.

    Only an admin sets it (see `TeamMemberSerializer.validate_hourly_rate`);
    managers read it because the roster prices their week off it. Blank means
    the statutory minimum, which is also the floor any explicit rate is checked
    against — nobody is paid below it.
    """
    return serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0.01"),
        **kwargs,
    )


def validate_store_matches_department(attrs, instance=None):
    """Keep `user.store` and `user.department.store` from drifting apart.

    A department is per store, so picking one settles the store too. Assigning
    somebody to the Deli in Balbriggan while their store says Palmerstown would
    scope their dockets to one branch and their roster to another, so it is
    refused rather than silently resolved either way.
    """
    department = attrs.get("department", getattr(instance, "department", None))
    if department is None:
        return attrs

    store_is_changing = "store" in attrs
    store = attrs["store"] if store_is_changing else getattr(instance, "store", None)

    if store is None:
        if store_is_changing and instance is not None and instance.store_id:
            raise serializers.ValidationError(
                {
                    "store_slug": (
                        f"They work in {department}. Move them to another department "
                        "before clearing their store."
                    )
                }
            )
        # No store yet: the department settles it.
        attrs["store"] = department.store
    elif store != department.store:
        raise serializers.ValidationError(
            {
                "department_slug": (
                    f"{department} is not in {store.name}. Pick a department at "
                    "their store."
                )
            }
        )
    return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of the signed-in user."""

    store = StoreSerializer(read_only=True)
    department = StoreDepartmentLabelSerializer(read_only=True)
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
            "department",
            "phone",
            "hourly_rate",
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
    department = StoreDepartmentLabelSerializer(read_only=True)
    department_slug = department_field(write_only=True, required=False)
    hourly_rate = hourly_rate_field()
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
            "department",
            "department_slug",
            "hourly_rate",
            "is_active",
            "last_login",
            "date_joined",
        )
        read_only_fields = ("id", "email", "full_name", "last_login", "date_joined")

    def validate_hourly_rate(self, value):
        """Pay is an admin's call, and never below the statutory minimum."""
        actor = self.context["request"].user
        if actor.role != User.Role.ADMIN:
            raise serializers.ValidationError("Only an admin can set what somebody is paid.")
        if value is not None and value < settings.MINIMUM_HOURLY_RATE:
            raise serializers.ValidationError(
                f"The minimum wage is €{settings.MINIMUM_HOURLY_RATE} an hour."
            )
        return value

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
        attrs = validate_store_matches_department(attrs, self.instance)

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
    # Required here and only here: a new colleague always gets a department,
    # while the accounts that predate this can be filled in as they come up.
    # It also settles `store_slug`, which is why that one stays optional.
    department_slug = department_field(required=True)
    hourly_rate = hourly_rate_field()

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
            "department_slug",
            "hourly_rate",
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

    def validate_hourly_rate(self, value):
        actor = self.context["request"].user
        if actor.role != User.Role.ADMIN:
            raise serializers.ValidationError("Only an admin can set what somebody is paid.")
        if value is not None and value < settings.MINIMUM_HOURLY_RATE:
            raise serializers.ValidationError(
                f"The minimum wage is €{settings.MINIMUM_HOURLY_RATE} an hour."
            )
        return value

    def validate(self, attrs):
        return validate_store_matches_department(attrs)

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        if user.role == User.Role.ADMIN:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        return user


class AdminBootstrapSerializer(serializers.Serializer):
    """Creates an admin account for whoever holds the shared setup code.

    Only ever creates admins — it exists so the first account can be made
    without shell access, and so a locked-out office can make another. Every
    other account is created by a manager on /team.
    """

    secret_code = serializers.CharField(write_only=True, trim_whitespace=False)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_email(self, value):
        normalized = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with that email already exists.")
        return normalized

    def validate_secret_code(self, value):
        expected = settings.ADMIN_BOOTSTRAP_CODE
        # The view refuses the request outright when no code is configured;
        # this is belt and braces so an empty code can never match.
        if not expected or not secrets.compare_digest(value, expected):
            raise serializers.ValidationError("That setup code is not valid.")
        return value

    def create(self, validated_data):
        validated_data.pop("secret_code")
        password = validated_data.pop("password")
        return User.objects.create_superuser(password=password, **validated_data)
