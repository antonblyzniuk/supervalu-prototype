from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel, UUIDTimeStampedModel

from . import constants


def signature_upload_to(instance, filename):
    return f"dockets/{instance.docket_id}/signatures/{instance.role}.png"


def photo_upload_to(instance, filename):
    return f"dockets/{instance.docket_id}/photos/{filename}"


class Docket(UUIDTimeStampedModel):
    """One saved docket sheet.

    Ambient/chilled dockets are weekly registers keyed on `week_ending`;
    returns and transfers are single-event dockets keyed on `docket_date`.
    The type-specific fields are nullable and validated in the serializer.
    """

    class Type(models.TextChoices):
        AMBIENT = constants.AMBIENT, _("Ambient")
        CHILLED = constants.CHILLED, _("Chilled")
        RETURNS = constants.RETURNS, _("Returns")
        TRANSFER = constants.TRANSFER, _("Transfer")

    store = models.ForeignKey("stores.Store", on_delete=models.PROTECT, related_name="dockets")
    docket_type = models.CharField(max_length=16, choices=Type.choices, db_index=True)

    week_ending = models.DateField(null=True, blank=True, db_index=True)
    docket_date = models.DateField(null=True, blank=True, db_index=True)

    reference = models.CharField(max_length=64, blank=True)
    docket_number = models.CharField(max_length=64, blank=True)
    department = models.CharField(max_length=64, blank=True)

    # Returns only.
    supplier = models.CharField(max_length=160, blank=True)
    reason = models.TextField(blank=True)

    # Transfer only.
    destination_store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        null=True,
        blank=True,
    )
    outgoing_staff_name = models.CharField(max_length=120, blank=True)

    manager_name = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dockets",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["store", "docket_type", "-created_at"])]

    def __str__(self):
        return f"{self.get_docket_type_display()} · {self.store.name} · {self.effective_date}"

    @property
    def effective_date(self):
        """The date this docket belongs to, whichever field the type uses."""
        return self.week_ending or self.docket_date or self.created_at.date()

    @property
    def is_category_type(self):
        return self.docket_type in constants.CATEGORY_TYPES

    def category_totals(self):
        """Sum each department column across this docket's lines."""
        keys = constants.category_keys(self.docket_type)
        totals = {key: Decimal("0.00") for key in keys}
        for line in self.lines.all():
            for key in keys:
                totals[key] += _to_decimal(line.amounts.get(key))
        return totals

    def recalculate_total(self, save=True):
        total = sum((line.total or Decimal("0.00") for line in self.lines.all()), Decimal("0.00"))
        self.total = total
        if save:
            Docket.objects.filter(pk=self.pk).update(total=total)
        return total


class DocketLine(models.Model):
    """A single row of a docket.

    Ambient/chilled lines use `line_date`/`supplier`/`amounts`; returns and
    transfer lines use `quantity`/`description`/`cost_price`/`retail_price`.
    `total` is what every report sums, so it is always populated.
    """

    docket = models.ForeignKey(Docket, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField(default=0)

    # Category-register lines.
    line_date = models.DateField(null=True, blank=True)
    supplier = models.CharField(max_length=160, blank=True)
    docket_number = models.CharField(max_length=64, blank=True)
    amounts = models.JSONField(default=dict, blank=True)
    comments = models.CharField(max_length=255, blank=True)

    # Item lines.
    quantity = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ("position", "id")

    def __str__(self):
        return f"{self.docket_id} line {self.position}"


class DocketSignature(TimeStampedModel):
    """A captured signature. One row per role, replaced on re-sign."""

    class Role(models.TextChoices):
        MANAGER = "manager", _("Manager")
        STAFF = "staff", _("Staff")
        BRANCH_MANAGER = "branch_manager", _("Branch Manager")
        OUTGOING_STAFF = "outgoing_staff", _("Outgoing Staff")
        OUTGOING_MANAGER = "outgoing_manager", _("Outgoing Manager")
        INCOMING_MANAGER = "incoming_manager", _("Incoming Manager")

    docket = models.ForeignKey(Docket, on_delete=models.CASCADE, related_name="signatures")
    role = models.CharField(max_length=32, choices=Role.choices)
    signed_name = models.CharField(max_length=120, blank=True)
    image = models.ImageField(upload_to=signature_upload_to)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(fields=("docket", "role"), name="unique_signature_per_role")
        ]

    def __str__(self):
        return f"{self.docket_id} {self.role}"


class DocketPhoto(TimeStampedModel):
    """A photo of the paper docket, with the capture stamp shown in reports."""

    docket = models.ForeignKey(Docket, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=photo_upload_to)
    caption = models.CharField(max_length=160, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self):
        return f"{self.docket_id} photo {self.pk}"


def _to_decimal(value):
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return Decimal("0.00")
