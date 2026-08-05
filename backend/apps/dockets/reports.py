"""Aggregation shared by the summary endpoint and the PDF/JSON exports."""

from collections import OrderedDict
from decimal import Decimal

from . import constants
from .models import Docket


def _decimal(value):
    if value in (None, ""):
        return Decimal("0.00")
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return Decimal("0.00")


def columns_for(docket_type):
    return [
        {"key": key, "label": label}
        for key, label in constants.CATEGORIES_BY_TYPE.get(docket_type, ())
    ]


def build_summary(queryset):
    """Group a docket queryset by type and by store, with column totals.

    Returned decimals are stringified so JSON keeps two-place money values.
    """
    dockets = list(
        queryset.select_related("store", "destination_store").prefetch_related("lines")
    )

    by_type = OrderedDict()
    for value, label in Docket.Type.choices:
        by_type[value] = {
            "docket_type": value,
            "label": label,
            "columns": columns_for(value),
            "docket_count": 0,
            "line_count": 0,
            "total": Decimal("0.00"),
            "category_totals": {key: Decimal("0.00") for key in constants.category_keys(value)},
        }

    by_store = OrderedDict()

    for docket in dockets:
        bucket = by_type[docket.docket_type]
        bucket["docket_count"] += 1
        bucket["total"] += docket.total or Decimal("0.00")

        store_bucket = by_store.setdefault(
            docket.store.slug,
            {
                "store": {
                    "slug": docket.store.slug,
                    "name": docket.store.name,
                    "code": docket.store.code,
                },
                "docket_count": 0,
                "total": Decimal("0.00"),
                "by_type": {value: Decimal("0.00") for value, _ in Docket.Type.choices},
            },
        )
        store_bucket["docket_count"] += 1
        store_bucket["total"] += docket.total or Decimal("0.00")
        store_bucket["by_type"][docket.docket_type] += docket.total or Decimal("0.00")

        keys = constants.category_keys(docket.docket_type)
        for line in docket.lines.all():
            bucket["line_count"] += 1
            for key in keys:
                bucket["category_totals"][key] += _decimal(line.amounts.get(key))

    grand_total = sum((d.total or Decimal("0.00") for d in dockets), Decimal("0.00"))

    return {
        "docket_count": len(dockets),
        "grand_total": str(grand_total),
        "by_type": [
            {
                **bucket,
                "total": str(bucket["total"]),
                "category_totals": {k: str(v) for k, v in bucket["category_totals"].items()},
            }
            for bucket in by_type.values()
        ],
        "by_store": [
            {
                **bucket,
                "total": str(bucket["total"]),
                "by_type": {k: str(v) for k, v in bucket["by_type"].items()},
            }
            for bucket in by_store.values()
        ],
    }
