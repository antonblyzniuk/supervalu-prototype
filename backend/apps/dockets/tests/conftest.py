import base64

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.stores.models import Store

# Smallest valid PNG — enough for ImageField/Pillow validation.
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
).decode()


@pytest.fixture
def stores(db):
    return {store.slug: store for store in Store.objects.all()}


@pytest.fixture
def staff_user(db, stores):
    return get_user_model().objects.create_user(
        email="staff@moriarty.ie", password="pw-12345678", store=stores["skerries"]
    )


@pytest.fixture
def manager_user(db, stores):
    return get_user_model().objects.create_user(
        email="manager@moriarty.ie",
        password="pw-12345678",
        store=stores["balbriggan"],
        role="manager",
    )


@pytest.fixture
def api(staff_user):
    client = APIClient()
    client.force_authenticate(staff_user)
    return client


@pytest.fixture
def manager_api(manager_user):
    client = APIClient()
    client.force_authenticate(manager_user)
    return client


@pytest.fixture
def ambient_payload():
    return {
        "docket_type": "ambient",
        "store": "skerries",
        "week_ending": "2026-08-08",
        "reference": "1871",
        "manager_name": "Aaron Doyle",
        "lines": [
            {
                "position": 0,
                "line_date": "2026-08-04",
                "supplier": "Musgrave",
                "docket_number": "A100",
                "amounts": {"groc": "120.50", "wine": "40.00"},
                "total": "160.50",
                "comments": "Full delivery",
            },
            {
                "position": 1,
                "line_date": "2026-08-05",
                "supplier": "Britvic",
                "docket_number": "A101",
                "amounts": {"groc": "39.50"},
                "total": "39.50",
            },
        ],
        "signatures": [
            {"role": "manager", "signed_name": "Aaron Doyle", "image": PNG_DATA_URL}
        ],
        "photos": [{"image": PNG_DATA_URL, "caption": "Docket A100"}],
    }


@pytest.fixture
def transfer_payload():
    return {
        "docket_type": "transfer",
        "store": "balbriggan",
        "destination_store": "palmerstown",
        "docket_date": "2026-08-05",
        "docket_number": "0851",
        "department": "Deli",
        "outgoing_staff_name": "Niamh",
        "lines": [
            {
                "position": 0,
                "quantity": "3 cases",
                "description": "Chicken fillets",
                "cost_price": "20.00",
                "retail_price": "35.00",
                "total": "60.00",
            }
        ],
    }
