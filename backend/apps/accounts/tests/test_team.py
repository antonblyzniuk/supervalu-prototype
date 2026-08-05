"""Manager-facing staff administration."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.stores.models import Store

User = get_user_model()
LIST_URL = reverse("accounts:team-list")


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def stores(db):
    return {store.slug: store for store in Store.objects.all()}


@pytest.fixture
def staff(db, stores):
    return User.objects.create_user(
        email="staff@moriarty.ie", password="pw-12345678", store=stores["skerries"]
    )


@pytest.fixture
def manager(db, stores):
    return User.objects.create_user(
        email="manager@moriarty.ie",
        password="pw-12345678",
        role=User.Role.MANAGER,
        store=stores["balbriggan"],
    )


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(email="admin@moriarty.ie", password="pw-12345678")


def test_staff_cannot_reach_team_administration(staff):
    assert client_for(staff).get(LIST_URL).status_code == 403


def test_manager_lists_the_team(manager, staff):
    response = client_for(manager).get(LIST_URL)
    assert response.status_code == 200
    emails = {row["email"] for row in response.data["results"]}
    assert {"staff@moriarty.ie", "manager@moriarty.ie"} <= emails


def test_manager_assigns_a_store(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"store_slug": "palmerstown"}, format="json")
    assert response.status_code == 200
    assert response.data["store"]["slug"] == "palmerstown"

    staff.refresh_from_db()
    assert staff.store.slug == "palmerstown"


def test_manager_can_clear_a_store_assignment(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"store_slug": None}, format="json")
    assert response.status_code == 200
    assert response.data["store"] is None


def test_manager_cannot_grant_admin(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"role": "admin"}, format="json")
    assert response.status_code == 400
    assert "admin" in str(response.data["role"]).lower()


def test_admin_can_grant_admin(admin, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(admin).patch(url, {"role": "admin"}, format="json")
    assert response.status_code == 200

    staff.refresh_from_db()
    assert staff.role == User.Role.ADMIN
    assert staff.is_staff is True  # Django admin access follows the app role.


def test_manager_cannot_change_their_own_role(manager):
    url = reverse("accounts:team-detail", args=[manager.pk])
    response = client_for(manager).patch(url, {"role": "staff"}, format="json")
    assert response.status_code == 400


def test_manager_onboards_a_colleague(manager, stores):
    response = client_for(manager).post(
        LIST_URL,
        {
            "email": "New.Hire@moriarty.ie",
            "first_name": "Orla",
            "role": "staff",
            "store_slug": "skerries",
            "password": "starter-pass-9931",
        },
        format="json",
    )
    assert response.status_code == 201, response.data

    created = User.objects.get(email="new.hire@moriarty.ie")
    assert created.store.slug == "skerries"
    assert created.check_password("starter-pass-9931")


def test_onboarding_rejects_a_weak_password(manager):
    response = client_for(manager).post(
        LIST_URL,
        {"email": "weak@moriarty.ie", "role": "staff", "password": "1234"},
        format="json",
    )
    assert response.status_code == 400
    assert "password" in response.data


def test_onboarding_rejects_a_duplicate_email(manager, staff):
    response = client_for(manager).post(
        LIST_URL,
        {"email": "STAFF@moriarty.ie", "role": "staff", "password": "starter-pass-9931"},
        format="json",
    )
    assert response.status_code == 400
    assert "email" in response.data


def test_delete_deactivates_instead_of_removing(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    assert client_for(manager).delete(url).status_code == 204

    staff.refresh_from_db()
    assert staff.is_active is False
    assert User.objects.filter(pk=staff.pk).exists()


def test_manager_cannot_deactivate_themselves(manager):
    url = reverse("accounts:team-detail", args=[manager.pk])
    assert client_for(manager).delete(url).status_code == 400


def test_password_reset_sets_a_new_password(manager, staff):
    url = reverse("accounts:team-set-password", args=[staff.pk])
    response = client_for(manager).post(url, {"password": "brand-new-pass-77"}, format="json")
    assert response.status_code == 200

    staff.refresh_from_db()
    assert staff.check_password("brand-new-pass-77")


def test_manager_cannot_reset_an_admin_password(manager, admin):
    url = reverse("accounts:team-set-password", args=[admin.pk])
    response = client_for(manager).post(url, {"password": "brand-new-pass-77"}, format="json")
    assert response.status_code == 403
