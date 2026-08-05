"""The shared-code admin bootstrap endpoint."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()
URL = reverse("accounts:bootstrap-admin")

CODE = "correct-horse-battery-staple-9931"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def enabled(settings):
    settings.ADMIN_BOOTSTRAP_CODE = CODE
    return settings


@pytest.fixture(autouse=True)
def _reset_throttles():
    """Throttle history is cached globally; clear it between tests."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def payload(**overrides):
    return {
        "secret_code": CODE,
        "email": "founder@moriartygroup.ie",
        "password": "a-solid-setup-pass-42",
        "first_name": "Anton",
        **overrides,
    }


def test_creates_an_admin_with_the_right_code(api, enabled, db):
    response = api.post(URL, payload(), format="json")
    assert response.status_code == 201, response.data

    user = User.objects.get(email="founder@moriartygroup.ie")
    assert user.role == User.Role.ADMIN
    assert user.is_superuser is True
    assert user.is_staff is True  # so Django admin is reachable too
    assert user.check_password("a-solid-setup-pass-42")
    assert response.data["email"] == "founder@moriartygroup.ie"
    assert "password" not in response.data


def test_endpoint_is_absent_when_no_code_is_configured(api, db, settings):
    settings.ADMIN_BOOTSTRAP_CODE = ""
    response = api.post(URL, payload(), format="json")
    assert response.status_code == 404
    assert not User.objects.exists()


def test_wrong_code_is_rejected(api, enabled, db):
    response = api.post(URL, payload(secret_code="not-the-code"), format="json")
    assert response.status_code == 400
    assert "secret_code" in response.data
    assert not User.objects.exists()


def test_empty_code_never_matches(api, enabled, db):
    response = api.post(URL, payload(secret_code=""), format="json")
    assert response.status_code == 400
    assert not User.objects.exists()


def test_weak_password_is_rejected(api, enabled, db):
    response = api.post(URL, payload(password="1234"), format="json")
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.exists()


def test_duplicate_email_is_rejected(api, enabled, db):
    User.objects.create_user(email="founder@moriartygroup.ie", password="pw-12345678")
    response = api.post(URL, payload(), format="json")
    assert response.status_code == 400
    assert "email" in response.data


def test_email_is_normalised_to_lowercase(api, enabled, db):
    response = api.post(URL, payload(email="Founder@MoriartyGroup.ie"), format="json")
    assert response.status_code == 201
    assert User.objects.get().email == "founder@moriartygroup.ie"


def test_repeated_wrong_guesses_are_throttled(api, enabled, db, settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK}
    codes = [payload(secret_code=f"guess-{i}") for i in range(12)]

    statuses = [api.post(URL, body, format="json").status_code for body in codes]
    assert 429 in statuses, "brute-forcing the setup code should hit the rate limit"
    assert not User.objects.exists()


def test_the_new_admin_can_sign_in(api, enabled, db):
    api.post(URL, payload(), format="json")

    token = api.post(
        reverse("accounts:token-obtain-pair"),
        {"email": "founder@moriartygroup.ie", "password": "a-solid-setup-pass-42"},
        format="json",
    )
    assert token.status_code == 200

    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    profile = me.get(reverse("accounts:me"))
    assert profile.data["role"] == "admin"
    assert profile.data["is_manager"] is True
