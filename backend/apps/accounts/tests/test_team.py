"""Manager-facing staff administration."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.departments.models import StoreDepartment
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
def deli(db, stores):
    """A department is per store, so an assignment always names a branch."""
    return StoreDepartment.objects.get(department__slug="deli", store=stores["skerries"])


@pytest.fixture
def staff(db, stores, deli):
    return User.objects.create_user(
        email="staff@moriarty.ie",
        password="pw-12345678",
        store=stores["skerries"],
        department=deli,
    )


@pytest.fixture
def unassigned(db):
    """Nobody's department, nobody's store — an account made before all this."""
    return User.objects.create_user(email="spare@moriarty.ie", password="pw-12345678")


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


def test_manager_assigns_a_store(manager, unassigned):
    url = reverse("accounts:team-detail", args=[unassigned.pk])
    response = client_for(manager).patch(url, {"store_slug": "palmerstown"}, format="json")
    assert response.status_code == 200
    assert response.data["store"]["slug"] == "palmerstown"

    unassigned.refresh_from_db()
    assert unassigned.store.slug == "palmerstown"


def test_manager_can_clear_a_store_assignment(manager, unassigned):
    unassigned.store = Store.objects.get(slug="skerries")
    unassigned.save(update_fields=["store"])

    url = reverse("accounts:team-detail", args=[unassigned.pk])
    response = client_for(manager).patch(url, {"store_slug": None}, format="json")
    assert response.status_code == 200
    assert response.data["store"] is None


def test_a_store_cannot_be_cleared_while_they_are_in_a_department(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"store_slug": None}, format="json")
    assert response.status_code == 400

    staff.refresh_from_db()
    assert staff.store.slug == "skerries"


def test_a_store_move_has_to_take_the_department_with_it(manager, staff):
    """Their roster and their dockets must not end up in different branches."""
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"store_slug": "palmerstown"}, format="json")
    assert response.status_code == 400
    assert "not in Palmerstown" in str(response.data["department_slug"])

    response = client_for(manager).patch(
        url,
        {"store_slug": "palmerstown", "department_slug": "deli-at-palmerstown"},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["store"]["slug"] == "palmerstown"
    assert response.data["department"]["slug"] == "deli-at-palmerstown"


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


def test_manager_onboards_a_colleague(manager, stores, deli):
    response = client_for(manager).post(
        LIST_URL,
        {
            "email": "New.Hire@moriarty.ie",
            "first_name": "Orla",
            "role": "staff",
            "store_slug": "skerries",
            "department_slug": "deli-at-skerries",
            "password": "starter-pass-9931",
        },
        format="json",
    )
    assert response.status_code == 201, response.data

    created = User.objects.get(email="new.hire@moriarty.ie")
    assert created.store.slug == "skerries"
    assert created.department == deli
    assert created.check_password("starter-pass-9931")


def test_onboarding_requires_a_department(manager):
    response = client_for(manager).post(
        LIST_URL,
        {
            "email": "no.dept@moriarty.ie",
            "role": "staff",
            "store_slug": "skerries",
            "password": "starter-pass-9931",
        },
        format="json",
    )
    assert response.status_code == 400
    assert "department_slug" in response.data
    assert not User.objects.filter(email="no.dept@moriarty.ie").exists()


def test_manager_moves_a_colleague_between_departments(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(
        url, {"department_slug": "bakery-at-skerries"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["department"]["department"]["slug"] == "bakery"
    assert response.data["department"]["store"]["slug"] == "skerries"

    staff.refresh_from_db()
    assert staff.department.slug == "bakery-at-skerries"
    # Their store did not move with it — the branch is in the same store.
    assert staff.store.slug == "skerries"


def test_a_colleague_cannot_be_put_in_another_store_department(manager, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(
        url, {"department_slug": "deli-at-balbriggan"}, format="json"
    )
    assert response.status_code == 400

    staff.refresh_from_db()
    assert staff.department.slug == "deli-at-skerries"


def test_a_department_settles_the_store_for_somebody_who_has_none(manager, unassigned):
    url = reverse("accounts:team-detail", args=[unassigned.pk])
    response = client_for(manager).patch(
        url, {"department_slug": "deli-at-balbriggan"}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["store"]["slug"] == "balbriggan"


def test_a_department_assignment_cannot_be_cleared(manager, staff, deli):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(manager).patch(url, {"department_slug": None}, format="json")
    assert response.status_code == 400

    staff.refresh_from_db()
    assert staff.department == deli


def test_team_filters_by_one_branch_or_by_the_whole_department(manager, staff, stores):
    other = User.objects.create_user(
        email="balbriggan.deli@moriarty.ie",
        password="pw-12345678",
        store=stores["balbriggan"],
        department=StoreDepartment.objects.get(
            department__slug="deli", store=stores["balbriggan"]
        ),
    )
    client = client_for(manager)

    one_branch = client.get(LIST_URL, {"department__slug": "deli-at-skerries"})
    assert [row["email"] for row in one_branch.data["results"]] == [staff.email]

    whole_department = client.get(LIST_URL, {"department__department__slug": "deli"})
    assert {row["email"] for row in whole_department.data["results"]} == {staff.email, other.email}


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
