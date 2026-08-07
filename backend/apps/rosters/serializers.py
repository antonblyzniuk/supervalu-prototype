from decimal import Decimal

from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import User

from .models import Shift, hours_from_minutes


def totals_for(shifts):
    """The block of figures every level of the board reports.

    One shape for a person, a department and a store, so the frontend renders
    them all the same way.
    """
    paid_minutes = sum(shift.paid_minutes for shift in shifts)
    return {
        "shift_count": len(shifts),
        "paid_minutes": paid_minutes,
        "hours": str(hours_from_minutes(paid_minutes)),
        # Summed from the per-shift figures, so a total always equals the rows
        # printed above it rather than a separately rounded number.
        "cost": str(sum((shift.cost for shift in shifts), Decimal("0.00"))),
    }


class ShiftSerializer(serializers.ModelSerializer):
    """A rostered day. Hours and cost are derived, never accepted from a client."""

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        source="user",
        write_only=True,
    )
    duration_minutes = serializers.IntegerField(read_only=True)
    paid_minutes = serializers.IntegerField(read_only=True)
    hours = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()
    hourly_rate = serializers.SerializerMethodField()

    class Meta:
        model = Shift
        fields = (
            "id",
            "user_id",
            "date",
            "start_time",
            "end_time",
            "break_minutes",
            "break_paid",
            "notes",
            "duration_minutes",
            "paid_minutes",
            "hours",
            "cost",
            "hourly_rate",
        )
        read_only_fields = ("id", "duration_minutes", "paid_minutes", "hours", "cost", "hourly_rate")
        # DRF would auto-build a unique-together validator for (user, date) and
        # report it under `non_field_errors` as "must make a unique set".
        # `validate` names the person and the day instead; the database
        # constraint is still the backstop.
        validators = ()

    def get_hours(self, obj) -> str:
        return str(hours_from_minutes(obj.paid_minutes))

    def get_cost(self, obj) -> str:
        return str(obj.cost)

    def get_hourly_rate(self, obj) -> str:
        return str(obj.hourly_rate)

    def validate(self, attrs):
        user = attrs.get("user", getattr(self.instance, "user", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        break_minutes = attrs.get(
            "break_minutes", getattr(self.instance, "break_minutes", 0)
        )
        break_paid = attrs.get("break_paid", getattr(self.instance, "break_paid", False))

        if user is not None and user.store_id is None:
            raise serializers.ValidationError(
                {
                    "user_id": (
                        f"{user.full_name} has no store yet, so there is no roster to put "
                        "them on. Assign them one on the team page first."
                    )
                }
            )

        if start == end:
            raise serializers.ValidationError(
                {"end_time": "A shift needs to finish at a different time than it starts."}
            )

        # Reuse the model's own arithmetic rather than repeating it, so the
        # check and the stored figures can never disagree.
        probe = Shift(date=date, start_time=start, end_time=end)
        duration = probe.duration_minutes
        if not break_paid and break_minutes >= duration:
            raise serializers.ValidationError(
                {
                    "break_minutes": (
                        f"An unpaid break of {break_minutes} minutes leaves nothing paid out "
                        f"of a {duration} minute shift."
                    )
                }
            )

        clash = Shift.objects.filter(user=user, date=date)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"date": f"{user.full_name} is already rostered on that day."}
            )

        # The store is the person's own — a shift is worked where they work.
        if user is not None:
            attrs["store"] = user.store
        return attrs


class RosterPersonSerializer(serializers.ModelSerializer):
    """One row of the board: who they are, what they cost, what they are on."""

    full_name = serializers.CharField(read_only=True)
    hourly_rate = serializers.SerializerMethodField()
    rate_is_default = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "role",
            "hourly_rate",
            "rate_is_default",
            "is_active",
        )
        read_only_fields = fields

    def get_hourly_rate(self, obj) -> str:
        return str(obj.effective_hourly_rate)

    def get_rate_is_default(self, obj) -> bool:
        """True when nobody has set a rate and the minimum wage is standing in."""
        return obj.hourly_rate is None


class RosterBoardSerializer(serializers.Serializer):
    """Read-only assembly of a store's week. Documents the shape for the schema."""

    store = serializers.DictField()
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    days = serializers.ListField(child=serializers.DateField())
    minimum_hourly_rate = serializers.CharField()
    departments = serializers.ListField(child=serializers.DictField())
    totals = serializers.DictField()


def build_board(store, week_start_date, days, store_departments, people, shifts):
    """Assemble the board: departments → people → their week.

    Everyone at the store appears, whether or not they are rostered, because a
    roster is as much about who is *not* on as who is.

    The trailing group catches anyone the store's own departments do not account
    for — nobody assigned yet, and anyone who has since moved branch or been
    deactivated while still holding shifts this week. Dropping them would leave
    the store total quietly bigger than the rows printed under it.
    """
    shifts_by_user = {}
    for shift in shifts:
        shifts_by_user.setdefault(shift.user_id, []).append(shift)

    def person_block(person):
        own = shifts_by_user.get(person.pk, [])
        return {
            "person": RosterPersonSerializer(person).data,
            "shifts": ShiftSerializer(own, many=True).data,
            "totals": totals_for(own),
        }

    # A person counts towards a department only if that department is one this
    # store runs — somebody who transferred now belongs to a branch elsewhere.
    own_departments = {store_department.pk for store_department in store_departments}
    people_by_department = {}
    for person in people:
        key = person.department_id if person.department_id in own_departments else None
        people_by_department.setdefault(key, []).append(person)

    groups = []
    for store_department in store_departments:
        members = people_by_department.get(store_department.pk, [])
        groups.append(
            {
                "id": store_department.pk,
                "slug": store_department.slug,
                "name": store_department.department.name,
                "code": store_department.department.code,
                "department_slug": store_department.department.slug,
                "people": [person_block(person) for person in members],
                "totals": totals_for(
                    [shift for person in members for shift in shifts_by_user.get(person.pk, [])]
                ),
            }
        )

    unassigned = people_by_department.get(None, [])
    if unassigned:
        groups.append(
            {
                "id": None,
                "slug": None,
                "name": "No department at this store",
                "code": "",
                "department_slug": None,
                "people": [person_block(person) for person in unassigned],
                "totals": totals_for(
                    [shift for person in unassigned for shift in shifts_by_user.get(person.pk, [])]
                ),
            }
        )

    return {
        "store": {"id": store.pk, "slug": store.slug, "name": store.name, "code": store.code},
        "week_start": week_start_date.isoformat(),
        "week_end": days[-1].isoformat(),
        "days": [day.isoformat() for day in days],
        "minimum_hourly_rate": str(settings.MINIMUM_HOURLY_RATE),
        "departments": groups,
        "totals": {
            **totals_for(shifts),
            "people_total": len(people),
            "people_rostered": len({shift.user_id for shift in shifts}),
        },
    }
