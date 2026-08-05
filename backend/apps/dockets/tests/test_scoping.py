"""Store scoping: staff are confined to their own branch, managers are not."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

LIST_URL = reverse("dockets:docket-list")


@pytest.fixture
def palmerstown_api(db, stores):
    user = get_user_model().objects.create_user(
        email="palmerstown.staff@moriarty.ie",
        password="pw-12345678",
        store=stores["palmerstown"],
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def storeless_api(db):
    user = get_user_model().objects.create_user(
        email="nostore@moriarty.ie", password="pw-12345678"
    )
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def filed(manager_api, ambient_payload, transfer_payload):
    """Ambient at Skerries, plus a Balbriggan → Palmerstown transfer."""
    manager_api.post(LIST_URL, ambient_payload, format="json")
    manager_api.post(LIST_URL, transfer_payload, format="json")


def test_staff_only_see_their_own_store(api, filed):
    response = api.get(LIST_URL)
    stores = {row["store_detail"]["slug"] for row in response.data["results"]}
    assert stores == {"skerries"}


def test_staff_see_transfers_arriving_at_their_store(palmerstown_api, filed):
    response = palmerstown_api.get(LIST_URL)
    assert response.data["count"] == 1
    assert response.data["results"][0]["docket_type"] == "transfer"


def test_manager_sees_every_store(manager_api, filed):
    response = manager_api.get(LIST_URL)
    assert response.data["count"] == 2


def test_staff_cannot_read_another_stores_docket(api, manager_api, transfer_payload):
    created = manager_api.post(LIST_URL, transfer_payload, format="json").data
    # A Skerries staff member is not party to a Balbriggan → Palmerstown transfer.
    url = reverse("dockets:docket-detail", args=[created["id"]])
    assert api.get(url).status_code == 404


def test_staff_cannot_file_for_another_store(api, ambient_payload):
    ambient_payload["store"] = "balbriggan"
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "own store" in str(response.data["store"])


def test_staff_without_a_store_are_blocked(storeless_api, ambient_payload, filed):
    assert storeless_api.get(LIST_URL).data["count"] == 0

    response = storeless_api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "no store assigned" in str(response.data["store"])


def test_summary_and_export_are_scoped_too(api, filed):
    summary = api.get(reverse("dockets:docket-summary"))
    assert summary.data["docket_count"] == 1
    assert [entry["store"]["slug"] for entry in summary.data["by_store"]] == ["skerries"]

    export = api.get(reverse("dockets:docket-export"), {"output": "json"})
    assert len(export.json()["dockets"]) == 1


def test_staff_cannot_widen_scope_with_a_store_filter(api, filed):
    """A hand-crafted `?store=` must not reach past the user's own branch."""
    response = api.get(LIST_URL, {"store": "balbriggan"})
    assert response.data["count"] == 0
