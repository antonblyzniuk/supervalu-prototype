from rest_framework import serializers

from apps.accounts.models import User
from apps.stores.models import Store
from apps.stores.serializers import StoreSerializer

from .models import Department, StoreDepartment

# Role counts are reported under these keys wherever a headcount is broken
# down, so the frontend can render one component for a store row and for the
# group total.
ROLE_KEYS = tuple(role.value for role in User.Role)


def role_breakdown(members):
    """{'staff': 3, 'manager': 1, 'admin': 0, 'total': 4} for active members."""
    counts = dict.fromkeys(ROLE_KEYS, 0)
    total = 0
    for member in members:
        if not member.is_active:
            continue
        total += 1
        if member.role in counts:
            counts[member.role] += 1
    return {**counts, "total": total}


class DepartmentPersonSerializer(serializers.ModelSerializer):
    """Compact staff row — used for heads of department and roster lists.

    Narrower than `TeamMemberSerializer` on purpose: the department screens are
    readable by more people than staff administration is.
    """

    store = StoreSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "employee_id", "store", "is_active")
        read_only_fields = fields


class DepartmentBriefSerializer(serializers.ModelSerializer):
    """The department kind, nested inside a branch instance."""

    class Meta:
        model = Department
        fields = ("id", "name", "slug", "code", "is_active")
        read_only_fields = fields


class StoreDepartmentLabelSerializer(serializers.ModelSerializer):
    """Names a branch — "Deli · Balbriggan" — and nothing more.

    Nested on user payloads, so it deliberately leaves out the headcounts: those
    read the roster, and a 25-row team page would otherwise fire 25 extra
    queries.
    """

    department = DepartmentBriefSerializer(read_only=True)
    store = StoreSerializer(read_only=True)

    class Meta:
        model = StoreDepartment
        fields = ("id", "slug", "department", "store")
        read_only_fields = fields


class StoreDepartmentRowSerializer(StoreDepartmentLabelSerializer):
    """A branch with its numbers — one line of the group-wide breakdown.

    "Deli in Balbriggan" and "Deli in general" are then the same shape read at
    two levels.
    """

    manager = DepartmentPersonSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta(StoreDepartmentLabelSerializer.Meta):
        fields = (*StoreDepartmentLabelSerializer.Meta.fields, "manager", "member_count", "roles")
        read_only_fields = fields

    # Both read the same prefetched roster, so a branch row costs no extra
    # query — every viewset that serializes one prefetches `members`.
    def get_member_count(self, obj) -> int:
        return sum(1 for member in obj.members.all() if member.is_active)

    def get_roles(self, obj) -> dict:
        return role_breakdown(obj.members.all())


class StoreDepartmentSerializer(StoreDepartmentRowSerializer):
    """A branch of a department on its own — what a staff user is assigned to.

    `department_slug` and `store_slug` are write-only and only meaningful on
    create: opening a department in a store is adding a row here, and moving an
    existing one to another store would take its staff with it, so neither can
    be changed afterwards.
    """

    department_slug = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Department.objects.filter(is_active=True),
        source="department",
        write_only=True,
    )
    store_slug = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Store.objects.filter(is_active=True),
        source="store",
        write_only=True,
    )
    manager_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="manager",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta(StoreDepartmentRowSerializer.Meta):
        fields = (
            *StoreDepartmentRowSerializer.Meta.fields,
            "department_slug",
            "store_slug",
            "manager_id",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "department",
            "store",
            "manager",
            "member_count",
            "roles",
            "created_at",
            "updated_at",
        )
        # DRF would auto-build a unique-together validator here and report it as
        # "the fields department_slug, store_slug must make a unique set", which
        # means nothing to whoever pressed the button. `validate` says it in
        # words instead; the database constraint is still the backstop.
        validators = ()

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            # Editing: the pair is fixed, so refuse it outright rather than
            # accepting a value that would be ignored.
            fields.pop("department_slug", None)
            fields.pop("store_slug", None)
        return fields

    def validate(self, attrs):
        department = attrs.get("department")
        store = attrs.get("store")
        if (
            department
            and store
            and StoreDepartment.objects.filter(department=department, store=store).exists()
        ):
            raise serializers.ValidationError(
                {"store_slug": f"{store.name} already runs {department.name}."}
            )
        return attrs

    def validate_manager_id(self, value):
        """The head of a branch department has to work in that branch.

        Named for the serializer field, not its `source` — DRF looks up
        `validate_<field_name>`.
        """
        if value is None or self.instance is None:
            return value
        store = self.instance.store
        if value.store_id and value.store_id != store.pk:
            raise serializers.ValidationError(
                f"{value.full_name} works at {value.store.name}, not {store.name}."
            )
        return value


class StoreDepartmentDetailSerializer(StoreDepartmentSerializer):
    """Adds the roster. Deactivated colleagues are included and flagged."""

    members = DepartmentPersonSerializer(many=True, read_only=True)

    class Meta(StoreDepartmentSerializer.Meta):
        fields = (*StoreDepartmentSerializer.Meta.fields, "members")


class DepartmentSerializer(serializers.ModelSerializer):
    """The department kind, with the group totals rolled up from its branches."""

    member_count = serializers.SerializerMethodField()
    store_count = serializers.SerializerMethodField()
    store_slugs = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Store.objects.filter(is_active=True),
        many=True,
        write_only=True,
        required=False,
        help_text="Stores that run it. Defaults to all of them; edit per store after.",
    )

    class Meta:
        model = Department
        fields = (
            "id",
            "name",
            "slug",
            "code",
            "description",
            "is_active",
            "member_count",
            "store_count",
            "store_slugs",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "member_count", "store_count", "created_at", "updated_at")

    def get_member_count(self, obj) -> int:
        """Active people in this department across every branch."""
        annotated = getattr(obj, "member_count", None)
        if annotated is not None:
            return annotated
        return User.objects.filter(department__department=obj, is_active=True).count()

    def get_store_count(self, obj) -> int:
        """Stores that run it — one row here per store that does."""
        annotated = getattr(obj, "store_count", None)
        if annotated is not None:
            return annotated
        return obj.store_departments.count()

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("A department needs a name.")
        clash = Department.objects.filter(name__iexact=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A department with that name already exists.")
        return name

    def create(self, validated_data):
        """Opens the new department in the stores that run it.

        Defaults to all of them, because that is the usual case and a department
        nobody can be assigned to is useless. Stores can be added and removed
        one at a time afterwards through `StoreDepartmentViewSet`.
        """
        stores = validated_data.pop("store_slugs", None)
        if stores is None:
            stores = list(Store.objects.filter(is_active=True))

        department = super().create(validated_data)
        for store in stores:
            StoreDepartment.objects.create(department=department, store=store)
        return department

    def update(self, instance, validated_data):
        # Which stores run it is edited per store, not by resubmitting a list —
        # a missing slug here must never silently delete a branch and its roster.
        validated_data.pop("store_slugs", None)
        return super().update(instance, validated_data)


class DepartmentDetailSerializer(DepartmentSerializer):
    """"Deli in general": the per-branch breakdown plus the combined roster."""

    stores = StoreDepartmentRowSerializer(source="store_departments", many=True, read_only=True)
    roles = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta(DepartmentSerializer.Meta):
        fields = (*DepartmentSerializer.Meta.fields, "stores", "roles", "members")

    def get_roles(self, obj) -> dict:
        return role_breakdown(self._members(obj))

    def get_members(self, obj):
        return DepartmentPersonSerializer(self._members(obj), many=True).data

    def _members(self, obj):
        """Everyone across the branches, prefetched by the viewset."""
        return [
            member
            for store_department in obj.store_departments.all()
            for member in store_department.members.all()
        ]
