from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

MINUTES_PER_HOUR = Decimal(60)
PENNY = Decimal("0.01")


def hours_from_minutes(minutes):
    """Minutes as decimal hours, to two places — 90 → 1.50."""
    return (Decimal(minutes) / MINUTES_PER_HOUR).quantize(PENNY, rounding=ROUND_HALF_UP)


def cost_of(minutes, hourly_rate):
    """What `minutes` at `hourly_rate` costs, rounded to the penny.

    Rounding happens per shift rather than on a week's total, so a person's
    total is always exactly the sum of the shifts shown above it.
    """
    return ((Decimal(minutes) / MINUTES_PER_HOUR) * hourly_rate).quantize(
        PENNY, rounding=ROUND_HALF_UP
    )


class Shift(TimeStampedModel):
    """One person's rostered day.

    The roster itself is not a record — it is this table read for one store and
    one trading week, which is why there is nothing to create before a manager
    can start filling a week in.

    One shift per person per day, enforced by a constraint. Split shifts (in for
    the morning, back for the evening) would need that lifted and the board's
    one-cell-per-day layout rethought.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    # Denormalised from `user.store` so the board stays a cheap query and a
    # filed roster keeps its shape if somebody later moves branch.
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="shifts",
    )
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Unpaid unless `break_paid` is set.",
    )
    break_paid = models.BooleanField(
        default=False,
        help_text="Paid breaks stay inside the paid hours; unpaid ones come off.",
    )
    notes = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts_rostered",
    )

    class Meta:
        ordering = ("date", "start_time", "user__email")
        constraints = [
            models.UniqueConstraint(fields=("user", "date"), name="one_shift_per_person_per_day")
        ]
        indexes = [models.Index(fields=("store", "date"))]

    def __str__(self):
        return f"{self.user.full_name} {self.date} {self.start_time:%H:%M}–{self.end_time:%H:%M}"

    @property
    def duration_minutes(self):
        """Clock-in to clock-out, breaks included.

        An end at or before the start is read as finishing the next day, so a
        22:00–02:00 close comes out as four hours rather than minus twenty.
        """
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        if end <= start:
            end += timedelta(days=1)
        return int((end - start).total_seconds() // 60)

    @property
    def unpaid_break_minutes(self):
        return 0 if self.break_paid else self.break_minutes

    @property
    def paid_minutes(self):
        """What actually gets paid — the span, less any unpaid break."""
        return max(self.duration_minutes - self.unpaid_break_minutes, 0)

    @property
    def hourly_rate(self):
        return self.user.effective_hourly_rate

    @property
    def cost(self):
        return cost_of(self.paid_minutes, self.hourly_rate)
