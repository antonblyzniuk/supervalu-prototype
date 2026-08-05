import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from apps.core.exceptions import StorageUnavailable
from apps.stores.models import Store
from apps.stores.serializers import StoreSerializer

from . import constants
from .fields import Base64ImageField
from .models import Docket, DocketLine, DocketPhoto, DocketSignature

logger = logging.getLogger(__name__)

# Docket.total is DecimalField(max_digits=12, decimal_places=2); anything at or
# above this would overflow the column and surface as a database error.
MAX_AMOUNT = Decimal("9999999999.99")

MAX_LINES = 200
MAX_PHOTOS = 24


class DocketLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocketLine
        fields = (
            "id",
            "position",
            "line_date",
            "supplier",
            "docket_number",
            "amounts",
            "comments",
            "quantity",
            "description",
            "cost_price",
            "retail_price",
            "total",
        )
        read_only_fields = ("id",)

    def validate_amounts(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Amounts must be an object of column → value.")
        cleaned = {}
        for key, raw in value.items():
            if raw in (None, ""):
                continue
            try:
                amount = Decimal(str(raw).strip().replace(",", ""))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise serializers.ValidationError(f"'{key}' is not a valid amount.") from exc
            if not amount.is_finite():
                raise serializers.ValidationError(f"'{key}' is not a valid amount.")
            if abs(amount) > MAX_AMOUNT:
                raise serializers.ValidationError(f"'{key}' is too large.")
            cleaned[key] = str(amount.quantize(Decimal("0.01")))
        return cleaned

    def validate_total(self, value):
        if value is not None and abs(value) > MAX_AMOUNT:
            raise serializers.ValidationError("Total is too large.")
        return value


class DocketSignatureSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = DocketSignature
        fields = ("id", "role", "signed_name", "image")
        read_only_fields = ("id",)


class DocketPhotoSerializer(serializers.ModelSerializer):
    image = Base64ImageField()

    class Meta:
        model = DocketPhoto
        fields = ("id", "image", "caption", "captured_at")
        read_only_fields = ("id",)


class DocketSerializer(serializers.ModelSerializer):
    """Read/write a whole docket — header, lines, signatures and photos — in one call.

    Nested collections are replace-on-write: whatever the client sends becomes
    the docket's full set of lines/signatures/photos, which matches how the form
    behaves (the user edits the whole sheet, then saves it).
    """

    lines = DocketLineSerializer(many=True)
    signatures = DocketSignatureSerializer(many=True, required=False)
    photos = DocketPhotoSerializer(many=True, required=False)

    store = serializers.SlugRelatedField(slug_field="slug", queryset=Store.objects.all())
    destination_store = serializers.SlugRelatedField(
        slug_field="slug", queryset=Store.objects.all(), required=False, allow_null=True
    )
    store_detail = StoreSerializer(source="store", read_only=True)
    destination_store_detail = StoreSerializer(source="destination_store", read_only=True)

    docket_type_display = serializers.CharField(source="get_docket_type_display", read_only=True)
    effective_date = serializers.DateField(read_only=True)
    category_totals = serializers.SerializerMethodField()
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Docket
        fields = (
            "id",
            "docket_type",
            "docket_type_display",
            "store",
            "store_detail",
            "destination_store",
            "destination_store_detail",
            "week_ending",
            "docket_date",
            "effective_date",
            "reference",
            "docket_number",
            "department",
            "supplier",
            "reason",
            "outgoing_staff_name",
            "manager_name",
            "notes",
            "total",
            "category_totals",
            "lines",
            "signatures",
            "photos",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "total", "created_at", "updated_at")

    def get_category_totals(self, obj):
        return {key: str(value) for key, value in obj.category_totals().items()}

    def validate(self, attrs):
        docket_type = attrs.get("docket_type", getattr(self.instance, "docket_type", None))
        errors = {}

        # Staff are pinned to their own store; managers file for any branch.
        actor = self.context["request"].user
        if not actor.is_manager:
            target = attrs.get("store", getattr(self.instance, "store", None))
            if actor.store_id is None:
                errors["store"] = (
                    "Your account has no store assigned. Ask a manager to assign one."
                )
            elif target and target.pk != actor.store_id:
                errors["store"] = "You can only file dockets for your own store."

        if docket_type in constants.CATEGORY_TYPES:
            if not attrs.get("week_ending", getattr(self.instance, "week_ending", None)):
                errors["week_ending"] = "Week ending date is required."
        else:
            if not attrs.get("docket_date", getattr(self.instance, "docket_date", None)):
                errors["docket_date"] = "Docket date is required."

        if docket_type == constants.RETURNS and not (
            attrs.get("supplier") or getattr(self.instance, "supplier", "")
        ):
            errors["supplier"] = "Supplier is required for a returns docket."

        if docket_type == constants.TRANSFER:
            store = attrs.get("store", getattr(self.instance, "store", None))
            destination = attrs.get(
                "destination_store", getattr(self.instance, "destination_store", None)
            )
            if destination is None:
                errors["destination_store"] = "Destination store is required for a transfer."
            elif store and destination == store:
                errors["destination_store"] = "Destination must differ from the sending store."

        lines = attrs.get("lines")
        if lines is not None:
            if not lines:
                errors["lines"] = "Add at least one line before saving."
            elif len(lines) > MAX_LINES:
                errors["lines"] = f"A docket cannot hold more than {MAX_LINES} lines."
            else:
                allowed = set(constants.category_keys(docket_type))
                running = Decimal("0.00")
                for index, line in enumerate(lines):
                    unknown = set(line.get("amounts", {})) - allowed
                    if unknown:
                        errors[f"lines[{index}].amounts"] = (
                            f"Unknown columns for a {docket_type} docket: {sorted(unknown)}"
                        )
                    # For a category register the row total is the sum of its
                    # columns by definition, so derive it rather than trusting
                    # whatever the client sent.
                    if docket_type in constants.CATEGORY_TYPES:
                        line["total"] = sum(
                            (Decimal(v) for v in line.get("amounts", {}).values()),
                            Decimal("0.00"),
                        )
                    running += line.get("total") or Decimal("0.00")

                if abs(running) > MAX_AMOUNT:
                    errors["lines"] = "The docket total is too large to store."

        photos = attrs.get("photos")
        if photos is not None and len(photos) > MAX_PHOTOS:
            errors["photos"] = f"A docket cannot hold more than {MAX_PHOTOS} photos."

        roles = attrs.get("signatures")
        if roles is not None:
            seen = [sig["role"] for sig in roles]
            if len(seen) != len(set(seen)):
                errors["signatures"] = "Only one signature per role."
            allowed_roles = set(constants.SIGNATURE_ROLES_BY_TYPE.get(docket_type, ()))
            invalid = set(seen) - allowed_roles
            if invalid:
                errors["signatures"] = (
                    f"Roles {sorted(invalid)} do not apply to a {docket_type} docket."
                )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        signatures = validated_data.pop("signatures", [])
        photos = validated_data.pop("photos", [])
        docket = Docket.objects.create(**validated_data)
        self._write_children(docket, lines, signatures, photos)
        docket.recalculate_total()
        docket.refresh_from_db()
        return docket

    @transaction.atomic
    def update(self, instance, validated_data):
        lines = validated_data.pop("lines", None)
        signatures = validated_data.pop("signatures", None)
        photos = validated_data.pop("photos", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines is not None:
            instance.lines.all().delete()
        if signatures is not None:
            instance.signatures.all().delete()
        if photos is not None:
            instance.photos.all().delete()

        self._write_children(instance, lines or [], signatures or [], photos or [])
        instance.recalculate_total()
        instance.refresh_from_db()
        return instance

    @staticmethod
    def _write_children(docket, lines, signatures, photos):
        DocketLine.objects.bulk_create(
            [
                DocketLine(docket=docket, **{**line, "position": line.get("position", index)})
                for index, line in enumerate(lines)
            ]
        )
        # Writing images is the only step that can fail on infrastructure rather
        # than input. Surface that as a 503 so the transaction rolls back and
        # the user is told the docket was not saved, instead of a bare 500.
        try:
            for signature in signatures:
                DocketSignature.objects.create(docket=docket, **signature)
            for photo in photos:
                DocketPhoto.objects.create(docket=docket, **photo)
        except OSError as exc:
            logger.error("Could not write docket upload to %s: %s", settings.MEDIA_ROOT, exc)
            raise StorageUnavailable() from exc


class DocketListSerializer(serializers.ModelSerializer):
    """Trimmed representation for list screens — no line or image payloads."""

    store_detail = StoreSerializer(source="store", read_only=True)
    destination_store_detail = StoreSerializer(source="destination_store", read_only=True)
    docket_type_display = serializers.CharField(source="get_docket_type_display", read_only=True)
    effective_date = serializers.DateField(read_only=True)
    line_count = serializers.IntegerField(read_only=True)
    photo_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Docket
        fields = (
            "id",
            "docket_type",
            "docket_type_display",
            "store_detail",
            "destination_store_detail",
            "week_ending",
            "docket_date",
            "effective_date",
            "reference",
            "docket_number",
            "supplier",
            "manager_name",
            "total",
            "line_count",
            "photo_count",
            "created_at",
        )
