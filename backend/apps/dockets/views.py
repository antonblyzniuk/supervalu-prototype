import json
import re
import unicodedata
from datetime import date

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsManager

from . import constants
from .filters import DocketFilter, week_end, week_start
from .models import Docket, DocketSignature
from .pdf import render_dockets_pdf
from .reports import build_summary, columns_for
from .serializers import DocketListSerializer, DocketSerializer

FILTER_PARAMS = [
    OpenApiParameter("store", str, description="Store slug; repeat or comma-separate for several."),
    OpenApiParameter("docket_type", str, description="ambient | chilled | returns | transfer."),
    OpenApiParameter("date_from", date),
    OpenApiParameter("date_to", date),
    OpenApiParameter("week_of", date, description="Any date inside the Sun–Sat trading week."),
    OpenApiParameter("q", str, description="Free-text search."),
]


def scoped_dockets(user):
    """Every docket the user is allowed to see.

    Managers and admins see the whole group. Staff see only their own store,
    plus transfers heading into it — the receiving branch needs to check off
    goods it did not raise the docket for. Staff with no store assigned see
    nothing until a manager assigns one.
    """
    queryset = Docket.objects.select_related("store", "destination_store", "created_by")
    if user.is_manager:
        return queryset
    if user.store_id is None:
        return queryset.none()
    return queryset.filter(Q(store_id=user.store_id) | Q(destination_store_id=user.store_id))


class DocketViewSet(viewsets.ModelViewSet):
    """Dockets for every store, filterable down to one store or one week.

    Deleting is restricted to managers; everyone signed in can read and file
    dockets, which mirrors how the paper process works on the shop floor.
    """

    filterset_class = DocketFilter
    ordering_fields = ("created_at", "week_ending", "docket_date", "total")
    ordering = ("-created_at",)
    search_fields = ()

    def get_queryset(self):
        queryset = scoped_dockets(self.request.user)
        if self.action == "list":
            return queryset.annotate(
                line_count=Count("lines", distinct=True),
                photo_count=Count("photos", distinct=True),
            )
        return queryset.prefetch_related("lines", "signatures", "photos")

    def get_serializer_class(self):
        return DocketListSerializer if self.action == "list" else DocketSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [IsManager()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def _filtered_queryset(self):
        """Apply the list filters to an un-annotated queryset for reports."""
        return self.filter_queryset(scoped_dockets(self.request.user))

    @extend_schema(
        parameters=FILTER_PARAMS,
        responses={200: dict},
        summary="Docket totals grouped by type and store",
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self._filtered_queryset()
        payload = build_summary(queryset)
        payload["filters"] = _echo_filters(request)
        return Response(payload)

    @extend_schema(
        parameters=FILTER_PARAMS
        + [
            OpenApiParameter(
                "output",
                str,
                description="json (default) or pdf. Both download as a file. "
                "Named `output` rather than `format` because DRF reserves `format` "
                "for content negotiation.",
            ),
            OpenApiParameter(
                "detail",
                bool,
                description="PDF only — include per-docket pages. Default true.",
            ),
        ],
        responses={200: bytes},
        summary="Download the filtered dockets as JSON or PDF",
    )
    @action(detail=False, methods=["get"])
    def export(self, request):
        export_format = request.query_params.get("output", "json").lower()
        queryset = self._filtered_queryset().prefetch_related("lines", "signatures", "photos")
        title, subtitle, slug = _export_labels(request, queryset)

        if export_format == "pdf":
            include_detail = request.query_params.get("detail", "true").lower() != "false"
            pdf_bytes = render_dockets_pdf(
                queryset, title=title, subtitle=subtitle, include_detail=include_detail
            )
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{slug}.pdf"'
            return response

        if export_format != "json":
            return Response({"detail": "output must be 'json' or 'pdf'."}, status=400)

        payload = {
            "title": title,
            "subtitle": subtitle,
            "exported_at": timezone.now().isoformat(),
            "filters": _echo_filters(request),
            "summary": build_summary(queryset),
            "dockets": DocketSerializer(
                queryset, many=True, context=self.get_serializer_context()
            ).data,
        }
        response = HttpResponse(
            json.dumps(payload, indent=2, default=str), content_type="application/json"
        )
        response["Content-Disposition"] = f'attachment; filename="{slug}.json"'
        return response

    @extend_schema(responses={200: dict}, summary="Column and signature definitions per type")
    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        """Lets the frontend build the four forms from one source of truth."""
        today = timezone.localdate()
        return Response(
            {
                "types": [
                    {
                        "value": value,
                        "label": label,
                        "shape": (
                            "categories" if value in constants.CATEGORY_TYPES else "items"
                        ),
                        "columns": columns_for(value),
                        "signature_roles": [
                            {"value": role, "label": _role_label(role)}
                            for role in constants.SIGNATURE_ROLES_BY_TYPE[value]
                        ],
                    }
                    for value, label in Docket.Type.choices
                ],
                "current_week": {
                    "start": week_start(today),
                    "end": week_end(today),
                },
            }
        )


def _role_label(role):
    return dict(DocketSignature.Role.choices).get(role, role.replace("_", " ").title())


def _echo_filters(request):
    keys = ("store", "docket_type", "date_from", "date_to", "week_of", "q")
    return {key: request.query_params.getlist(key) or None for key in keys}


def _export_labels(request, queryset):
    """Human title + filename stem describing exactly what was exported."""
    stores = sorted({docket.store.name for docket in queryset[:500]})
    store_param = request.query_params.getlist("store")
    if not store_param:
        scope = "All stores"
    elif len(stores) == 1:
        scope = stores[0]
    else:
        scope = ", ".join(stores) or "Selected stores"

    types = request.query_params.getlist("docket_type")
    type_label = ", ".join(t.title() for t in types) if types else "All docket types"

    week_of = request.query_params.get("week_of")
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if week_of:
        parsed = date.fromisoformat(week_of)
        period = f"Week {week_start(parsed):%d %b} – {week_end(parsed):%d %b %Y}"
    elif date_from or date_to:
        period = f"{date_from or 'start'} to {date_to or 'today'}"
    else:
        period = "All dates"

    title = "Docket Register"
    subtitle = f"{scope} · {type_label} · {period}"
    slug = _slugify_filename("-".join(("dockets", scope, type_label, period)))
    return title, subtitle, slug


def _slugify_filename(value):
    """ASCII-only stem — anything else makes Django emit an RFC 2047 header
    that several browsers save as a mangled filename."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return (cleaned or "dockets")[:120]
