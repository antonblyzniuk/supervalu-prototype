from datetime import date as date_cls
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.serializers import DateField

from apps.accounts.models import User
from apps.core.permissions import IsManager
from apps.departments.models import StoreDepartment

# The trading week is defined once, for the paper top sheets; a roster runs on
# the same Sunday→Saturday week so the two line up.
from apps.dockets.filters import week_start
from apps.stores.models import Store

from .models import Shift
from .pdf import render_roster_pdf
from .serializers import RosterBoardSerializer, ShiftSerializer, build_board

STORE_PARAM = OpenApiParameter("store", str, description="Store slug.", required=True)
WEEK_PARAM = OpenApiParameter(
    "week", OpenApiTypes.DATE, description="Any date in the week. Defaults to today."
)
DEPARTMENT_PARAM = OpenApiParameter(
    "department",
    str,
    description="Department slugs, repeated or comma separated. Omit for every department.",
)


class ShiftViewSet(viewsets.ModelViewSet):
    """Rostering people on and off. Manager and admin only.

    There is no roster record to create first — a shift is the roster, and the
    board is this table read for one store and one week.
    """

    permission_classes = (IsManager,)
    serializer_class = ShiftSerializer
    queryset = Shift.objects.select_related("user", "store").order_by("date", "start_time")
    filterset_fields = ("store__slug", "user", "date")
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


def _requested_store(request):
    store_slug = request.query_params.get("store")
    if not store_slug:
        raise ValidationError({"store": "Name a store to build the roster for."})
    return get_object_or_404(Store, slug=store_slug)


def _requested_week(request):
    raw = request.query_params.get("week")
    return DateField().to_internal_value(raw) if raw else date_cls.today()


def _day_label(day):
    """"2 Aug", matching how the week reads on screen."""
    return f"{day.day} {day.strftime('%b')}"


def _requested_departments(request):
    """Department slugs to keep, or None for every department the store runs.

    Accepts `?department=deli&department=bakery` and `?department=deli,bakery`,
    because the frontend sends a list as one comma-separated value.
    """
    raw = request.query_params.getlist("department")
    slugs = [slug.strip() for value in raw for slug in value.split(",") if slug.strip()]
    return slugs or None


def collect_board(store, anchor, department_slugs=None):
    """Everyone at a store for one trading week, optionally only some departments.

    Shared by the screen and the export, so a downloaded PDF can never disagree
    with what the manager was looking at.
    """
    start = week_start(anchor)
    days = [start + timedelta(days=offset) for offset in range(7)]

    store_departments = (
        StoreDepartment.objects.filter(store=store)
        .select_related("department")
        .order_by("department__name")
    )
    if department_slugs is not None:
        store_departments = store_departments.filter(department__slug__in=department_slugs)
    store_departments = list(store_departments)

    if department_slugs is not None:
        # A slug that matches nothing would otherwise hand back an empty roster
        # that looks perfectly valid — an export of nobody, silently. Say so.
        matched = {sd.department.slug for sd in store_departments}
        unknown = [slug for slug in department_slugs if slug not in matched]
        if unknown:
            raise ValidationError(
                {
                    "department": (
                        f"{store.name} does not run: {', '.join(sorted(unknown))}. "
                        "Use the department's slug, not the branch's."
                    )
                }
            )

    people = list(
        User.objects.filter(store=store, is_active=True)
        .select_related("department", "department__department")
        .order_by("department__department__name", "first_name", "last_name", "email")
    )
    shifts = list(
        Shift.objects.filter(store=store, date__range=(days[0], days[-1])).select_related("user")
    )

    if department_slugs is None:
        # Anyone holding a shift this week has to appear even if they have since
        # moved branch or been deactivated, or the store total would count hours
        # against a row nobody can see.
        missing = {shift.user_id for shift in shifts} - {person.pk for person in people}
        if missing:
            people += list(
                User.objects.filter(pk__in=missing).select_related(
                    "department", "department__department"
                )
            )
    else:
        # Narrowed to some departments: only those people, and only their hours,
        # so the totals describe exactly what was asked for.
        keep = {store_department.pk for store_department in store_departments}
        people = [person for person in people if person.department_id in keep]
        person_ids = {person.pk for person in people}
        shifts = [shift for shift in shifts if shift.user_id in person_ids]

    return build_board(store, start, days, store_departments, people, shifts), days


@extend_schema(
    summary="A store's roster for one trading week",
    parameters=[STORE_PARAM, WEEK_PARAM],
    responses={200: RosterBoardSerializer},
)
@api_view(["GET"])
@permission_classes([IsManager])
def roster_board(request):
    """Everyone at a store, grouped by department, with their week and its cost.

    Creates nothing: opening a week that nobody has rostered yet returns the
    same board with empty cells, so there is no draft state to get stuck in.
    """
    store = _requested_store(request)
    board, _days = collect_board(store, _requested_week(request))
    return Response(board)


@extend_schema(
    summary="Download a roster",
    description=(
        "`output=pdf` for the printable week, `output=json` for the same figures. "
        "Named `output` rather than `format` because DRF reserves `format` for "
        "content negotiation."
    ),
    parameters=[
        STORE_PARAM,
        WEEK_PARAM,
        DEPARTMENT_PARAM,
        OpenApiParameter("output", str, description="json (default) or pdf."),
    ],
    responses={200: OpenApiTypes.BINARY},
)
@api_view(["GET"])
@permission_classes([IsManager])
def roster_export(request):
    """The same board the screen shows, as a file — whole store or a department."""
    store = _requested_store(request)
    anchor = _requested_week(request)
    departments = _requested_departments(request)

    board, days = collect_board(store, anchor, departments)

    scope = "All departments"
    if departments:
        named = [group["name"] for group in board["departments"] if group["slug"]]
        scope = ", ".join(named) if named else "No matching department"

    title = f"Roster — {store.name}"
    week_label = f"{_day_label(days[0])} – {_day_label(days[-1])} {days[-1].year}"
    subtitle = f"{scope} · {week_label}"
    stem = slugify(f"roster-{store.slug}-{scope}-{board['week_start']}")

    output = request.query_params.get("output", "json").lower()
    if output == "pdf":
        response = HttpResponse(
            render_roster_pdf(board, days, title=title, subtitle=subtitle),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="{stem}.pdf"'
        return response

    if output != "json":
        return Response({"detail": "output must be 'json' or 'pdf'."}, status=400)

    return Response({"title": title, "subtitle": subtitle, **board})
