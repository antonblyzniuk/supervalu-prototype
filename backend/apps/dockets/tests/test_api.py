from decimal import Decimal

import pytest
from django.urls import reverse

from apps.dockets.models import Docket

LIST_URL = reverse("dockets:docket-list")


def test_create_ambient_docket_with_children(api, ambient_payload):
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201, response.data

    docket = Docket.objects.get()
    assert docket.lines.count() == 2
    assert docket.signatures.count() == 1
    assert docket.photos.count() == 1
    # Header total is derived from the lines, never trusted from the client.
    assert docket.total == Decimal("200.00")
    assert docket.created_by.email == "staff@moriarty.ie"
    assert response.data["category_totals"]["groc"] == "160.00"


def test_week_ending_is_required_for_category_dockets(api, ambient_payload):
    ambient_payload.pop("week_ending")
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "week_ending" in response.data


def test_unknown_category_column_is_rejected(api, ambient_payload):
    ambient_payload["lines"][0]["amounts"] = {"beef": "10.00"}
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "lines[0].amounts" in response.data


def test_transfer_requires_a_different_destination(manager_api, transfer_payload):
    transfer_payload["destination_store"] = "balbriggan"
    response = manager_api.post(LIST_URL, transfer_payload, format="json")
    assert response.status_code == 400
    assert "destination_store" in response.data


def test_transfer_docket_round_trips(manager_api, transfer_payload):
    response = manager_api.post(LIST_URL, transfer_payload, format="json")
    assert response.status_code == 201, response.data
    assert response.data["destination_store_detail"]["name"] == "Palmerstown"
    assert response.data["total"] == "60.00"


def test_update_replaces_lines_and_recalculates(api, ambient_payload):
    created = api.post(LIST_URL, ambient_payload, format="json").data
    url = reverse("dockets:docket-detail", args=[created["id"]])

    patched = api.patch(
        url,
        {"lines": [{"position": 0, "supplier": "Musgrave", "amounts": {"groc": "10"}, "total": "10.00"}]},
        format="json",
    )
    assert patched.status_code == 200, patched.data
    assert patched.data["total"] == "10.00"
    assert len(patched.data["lines"]) == 1


@pytest.mark.parametrize("store_filter,expected", [("skerries", 1), ("balbriggan", 1), (None, 2)])
def test_store_filter(manager_api, ambient_payload, transfer_payload, store_filter, expected):
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")

    params = {"store": store_filter} if store_filter else {}
    response = manager_api.get(LIST_URL, params)
    assert response.data["count"] == expected


def test_summary_groups_by_store_and_type(manager_api, ambient_payload, transfer_payload):
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")

    response = manager_api.get(reverse("dockets:docket-summary"))
    assert response.status_code == 200
    assert response.data["docket_count"] == 2
    assert response.data["grand_total"] == "260.00"

    ambient = next(b for b in response.data["by_type"] if b["docket_type"] == "ambient")
    assert ambient["category_totals"]["groc"] == "160.00"
    assert {s["store"]["slug"] for s in response.data["by_store"]} == {"skerries", "balbriggan"}


def test_summary_respects_store_filter(manager_api, ambient_payload, transfer_payload):
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")

    response = manager_api.get(reverse("dockets:docket-summary"), {"store": "skerries"})
    assert response.data["docket_count"] == 1
    assert response.data["grand_total"] == "200.00"


def test_export_json_downloads_full_dockets(api, ambient_payload):
    api.post(LIST_URL, ambient_payload, format="json")
    response = api.get(reverse("dockets:docket-export"), {"output": "json"})
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert "attachment;" in response["Content-Disposition"]

    payload = response.json()
    assert payload["summary"]["docket_count"] == 1
    assert len(payload["dockets"][0]["lines"]) == 2


def test_export_pdf_returns_a_pdf(manager_api, ambient_payload, transfer_payload):
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")

    response = manager_api.get(reverse("dockets:docket-export"), {"output": "pdf"})
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    body = b"".join(response.streaming_content) if response.streaming else response.content
    assert body.startswith(b"%PDF-")
    assert len(body) > 1500


def test_export_pdf_for_one_store(manager_api, ambient_payload, transfer_payload):
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")

    response = manager_api.get(reverse("dockets:docket-export"), {"output": "pdf", "store": "skerries"})
    assert response.status_code == 200
    assert "skerries" in response["Content-Disposition"].lower()


def test_meta_lists_columns_for_every_type(api):
    response = api.get(reverse("dockets:docket-meta"))
    assert response.status_code == 200
    types = {t["value"]: t for t in response.data["types"]}
    assert [c["key"] for c in types["chilled"]["columns"]][:3] == ["beef", "lamb", "pork"]
    assert types["returns"]["shape"] == "items"
    assert [r["value"] for r in types["transfer"]["signature_roles"]] == [
        "outgoing_staff",
        "outgoing_manager",
        "incoming_manager",
    ]


def test_staff_cannot_delete_but_manager_can(api, manager_api, ambient_payload):
    created = manager_api.post(LIST_URL, ambient_payload, format="json").data
    url = reverse("dockets:docket-detail", args=[created["id"]])

    assert api.delete(url).status_code == 403
    assert manager_api.delete(url).status_code == 204


def test_anonymous_access_is_rejected(client):
    assert client.get(LIST_URL).status_code == 401
