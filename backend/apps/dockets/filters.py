from datetime import date, timedelta

import django_filters
from django.db.models import Q

from .models import Docket


def week_start(value: date) -> date:
    """Trading week runs Sunday → Saturday, matching the paper top sheets."""
    return value - timedelta(days=(value.weekday() + 1) % 7)


def week_end(value: date) -> date:
    return week_start(value) + timedelta(days=6)


class DocketFilter(django_filters.FilterSet):
    """Filters shared by the list, summary and export endpoints.

    `store` accepts the slug and may be repeated (`?store=skerries&store=malahide`);
    leaving it off means every store, which is what the group-wide reports use.
    """

    store = django_filters.BaseInFilter(field_name="store__slug", lookup_expr="in")
    docket_type = django_filters.BaseInFilter(field_name="docket_type", lookup_expr="in")
    date_from = django_filters.DateFilter(method="filter_date_from")
    date_to = django_filters.DateFilter(method="filter_date_to")
    week_of = django_filters.DateFilter(method="filter_week_of")
    q = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Docket
        fields = ("store", "docket_type", "date_from", "date_to", "week_of", "q")

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(
            Q(week_ending__gte=value)
            | Q(docket_date__gte=value)
            | Q(week_ending__isnull=True, docket_date__isnull=True, created_at__date__gte=value)
        )

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(
            Q(week_ending__lte=value)
            | Q(docket_date__lte=value)
            | Q(week_ending__isnull=True, docket_date__isnull=True, created_at__date__lte=value)
        )

    def filter_week_of(self, queryset, name, value):
        start, end = week_start(value), week_end(value)
        return self.filter_date_to(self.filter_date_from(queryset, name, start), name, end)

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(reference__icontains=value)
            | Q(docket_number__icontains=value)
            | Q(supplier__icontains=value)
            | Q(manager_name__icontains=value)
            | Q(department__icontains=value)
            | Q(lines__supplier__icontains=value)
            | Q(lines__description__icontains=value)
        ).distinct()
