"""Departments: a group-wide kind, its per-store branches, and who sees what."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.departments.models import Department, StoreDepartment
from apps.stores.models import Store

User = get_user_model()
LIST_URL = reverse("departments:department-list")
BRANCH_LIST_URL = reverse("departments:store-department-list")


def detail_url(slug):
    return reverse("departments:department-detail", args=[slug])


def branch_url(slug):
    return reverse("departments:store-department-detail", args=[slug])


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def stores(db):
    return {store.slug: store for store in Store.objects.all()}


@pytest.fixture
def deli(db):
    return Department.objects.get(slug="deli")


@pytest.fixture
def deli_balbriggan(deli, stores):
    return StoreDepartment.objects.get(department=deli, store=stores["balbriggan"])


@pytest.fixture
def deli_skerries(deli, stores):
    return StoreDepartment.objects.get(department=deli, store=stores["skerries"])


@pytest.fixture
def staff(db, deli_balbriggan):
    return User.objects.create_user(
        email="staff@moriarty.ie",
        password="pw-12345678",
        store=deli_balbriggan.store,
        department=deli_balbriggan,
    )


@pytest.fixture
def other_store_staff(db, deli_skerries):
    """Same department, different branch — the person staff must not see."""
    return User.objects.create_user(
        email="skerries@moriarty.ie",
        password="pw-12345678",
        store=deli_skerries.store,
        department=deli_skerries,
    )


@pytest.fixture
def manager(db):
    return User.objects.create_user(
        email="manager@moriarty.ie", password="pw-12345678", role=User.Role.MANAGER
    )


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(email="admin@moriarty.ie", password="pw-12345678")


# --------------------------------------------------------------- provisioning


def test_every_department_is_opened_in_every_store(db):
    assert Department.objects.count() >= 10
    stores = Store.objects.filter(is_active=True).count()
    for department in Department.objects.all():
        assert department.store_departments.count() == stores


def test_a_new_department_opens_in_every_store_by_default(admin):
    response = client_for(admin).post(LIST_URL, {"name": "Flowers & Plants"}, format="json")
    assert response.status_code == 201
    assert response.data["slug"] == "flowers-plants"

    created = Department.objects.get(slug="flowers-plants")
    assert set(created.store_departments.values_list("store__slug", flat=True)) == {
        "balbriggan",
        "palmerstown",
        "skerries",
    }
    assert created.store_departments.filter(slug="flowers-plants-at-skerries").exists()


def test_a_new_department_can_open_in_chosen_stores_only(admin):
    """Not every branch runs every department."""
    response = client_for(admin).post(
        LIST_URL,
        {"name": "Fishmonger", "store_slugs": ["balbriggan", "skerries"]},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["store_count"] == 2

    created = Department.objects.get(slug="fishmonger")
    assert set(created.store_departments.values_list("store__slug", flat=True)) == {
        "balbriggan",
        "skerries",
    }


def test_editing_a_department_never_touches_which_stores_run_it(admin, deli):
    """A missing slug must not silently delete a branch and its roster."""
    response = client_for(admin).patch(
        detail_url("deli"), {"name": "Deli Counter", "store_slugs": []}, format="json"
    )
    assert response.status_code == 200
    assert deli.store_departments.count() == 3


# ------------------------------------------------------------------- the kind


def test_anonymous_is_refused():
    assert APIClient().get(LIST_URL).status_code == 401
    assert APIClient().get(BRANCH_LIST_URL).status_code == 401


def test_staff_cannot_see_the_group_wide_view(staff):
    """Pooling every branch is exactly what a staff user must not see."""
    assert client_for(staff).get(LIST_URL).status_code == 403
    assert client_for(staff).get(detail_url("deli")).status_code == 403


def test_manager_reads_the_group_wide_list(manager, staff, other_store_staff):
    response = client_for(manager).get(LIST_URL)
    assert response.status_code == 200
    row = next(entry for entry in response.data if entry["slug"] == "deli")
    # Both branches pooled.
    assert row["member_count"] == 2
    assert row["store_count"] == 3


@pytest.mark.parametrize("actor", ["staff", "manager"])
def test_only_admins_may_create_a_department(actor, request):
    user = request.getfixturevalue(actor)
    response = client_for(user).post(LIST_URL, {"name": "Flowers"}, format="json")
    assert response.status_code == 403
    assert not Department.objects.filter(name="Flowers").exists()


def test_duplicate_names_are_refused_case_insensitively(admin, deli):
    assert client_for(admin).post(LIST_URL, {"name": "  deli "}, format="json").status_code == 400


def test_renaming_keeps_the_slug_stable(admin, deli):
    response = client_for(admin).patch(detail_url("deli"), {"name": "Delicatessen"}, format="json")
    assert response.status_code == 200
    assert response.data["slug"] == "deli"


# ------------------------------------------------------- combined statistics


def test_group_view_breaks_the_headcount_down_by_store(manager, staff, other_store_staff):
    response = client_for(manager).get(detail_url("deli"))
    assert response.status_code == 200

    assert response.data["member_count"] == 2
    by_store = {row["store"]["slug"]: row for row in response.data["stores"]}
    assert by_store["balbriggan"]["member_count"] == 1
    assert by_store["skerries"]["member_count"] == 1
    assert by_store["palmerstown"]["member_count"] == 0

    emails = {member["email"] for member in response.data["members"]}
    assert emails == {"staff@moriarty.ie", "skerries@moriarty.ie"}


def test_group_view_breaks_the_headcount_down_by_role(manager, staff, deli_balbriggan):
    lead = User.objects.create_user(
        email="lead@moriarty.ie",
        password="pw-12345678",
        role=User.Role.MANAGER,
        store=deli_balbriggan.store,
        department=deli_balbriggan,
    )
    response = client_for(manager).get(detail_url("deli"))

    assert response.data["roles"] == {"staff": 1, "manager": 1, "admin": 0, "total": 2}
    balbriggan = next(r for r in response.data["stores"] if r["store"]["slug"] == "balbriggan")
    assert balbriggan["roles"] == {"staff": 1, "manager": 1, "admin": 0, "total": 2}
    assert lead.department == deli_balbriggan


def test_statistics_ignore_deactivated_people(manager, staff):
    staff.is_active = False
    staff.save(update_fields=["is_active"])

    response = client_for(manager).get(detail_url("deli"))
    assert response.data["member_count"] == 0
    assert response.data["roles"]["total"] == 0
    # Still listed on the roster, flagged, so a manager can see who left.
    assert response.data["members"][0]["is_active"] is False


# ------------------------------------------------------- branches and scoping


def test_staff_see_only_their_own_branch(staff, other_store_staff):
    response = client_for(staff).get(BRANCH_LIST_URL)
    assert response.status_code == 200
    assert [row["slug"] for row in response.data] == ["deli-at-balbriggan"]


def test_staff_cannot_open_the_same_department_in_another_store(staff, deli_skerries):
    assert client_for(staff).get(branch_url(deli_skerries.slug)).status_code == 404


def test_staff_cannot_open_another_department_in_their_own_store(staff, stores):
    bakery = StoreDepartment.objects.get(
        department__slug="bakery", store=stores["balbriggan"]
    )
    assert client_for(staff).get(branch_url(bakery.slug)).status_code == 404


def test_staff_with_no_department_see_nothing(db, stores):
    nobody = User.objects.create_user(
        email="nobody@moriarty.ie", password="pw-12345678", store=stores["skerries"]
    )
    assert client_for(nobody).get(BRANCH_LIST_URL).data == []


def test_staff_see_their_own_roster(staff, other_store_staff, deli_balbriggan):
    colleague = User.objects.create_user(
        email="colleague@moriarty.ie",
        password="pw-12345678",
        store=deli_balbriggan.store,
        department=deli_balbriggan,
    )
    response = client_for(staff).get(branch_url(deli_balbriggan.slug))
    assert response.status_code == 200
    emails = {member["email"] for member in response.data["members"]}
    assert emails == {staff.email, colleague.email}
    assert other_store_staff.email not in emails


def test_manager_sees_every_branch(manager):
    response = client_for(manager).get(BRANCH_LIST_URL)
    assert response.status_code == 200
    assert len(response.data) == StoreDepartment.objects.count()


def test_manager_filters_one_department_to_one_store(manager):
    response = client_for(manager).get(
        BRANCH_LIST_URL, {"department__slug": "deli", "store__slug": "balbriggan"}
    )
    assert [row["slug"] for row in response.data] == ["deli-at-balbriggan"]


# ------------------------------------------------------------ branch editing


@pytest.mark.parametrize("actor", ["staff", "manager"])
def test_only_admins_may_edit_a_branch(actor, request, deli_balbriggan):
    user = request.getfixturevalue(actor)
    response = client_for(user).patch(
        branch_url(deli_balbriggan.slug), {"notes": "hijacked"}, format="json"
    )
    assert response.status_code in (403, 404)
    deli_balbriggan.refresh_from_db()
    assert deli_balbriggan.notes == ""


def test_admin_sets_the_head_of_a_branch(admin, deli_balbriggan, staff):
    response = client_for(admin).patch(
        branch_url(deli_balbriggan.slug), {"manager_id": staff.pk}, format="json"
    )
    assert response.status_code == 200
    assert response.data["manager"]["email"] == staff.email


def test_the_head_of_a_branch_has_to_work_in_that_branch(admin, deli_balbriggan, other_store_staff):
    response = client_for(admin).patch(
        branch_url(deli_balbriggan.slug), {"manager_id": other_store_staff.pk}, format="json"
    )
    assert response.status_code == 400


# ------------------------------------------- adding and removing per store


@pytest.mark.parametrize("actor", ["staff", "manager"])
def test_only_admins_may_open_a_department_in_a_store(actor, request, deli, deli_skerries):
    deli_skerries.delete()
    user = request.getfixturevalue(actor)
    response = client_for(user).post(
        BRANCH_LIST_URL, {"department_slug": "deli", "store_slug": "skerries"}, format="json"
    )
    assert response.status_code == 403


def test_admin_opens_a_department_in_one_store(admin, deli, deli_skerries):
    deli_skerries.delete()
    response = client_for(admin).post(
        BRANCH_LIST_URL, {"department_slug": "deli", "store_slug": "skerries"}, format="json"
    )
    assert response.status_code == 201, response.data
    assert response.data["slug"] == "deli-at-skerries"
    assert response.data["store"]["slug"] == "skerries"
    assert response.data["member_count"] == 0


def test_a_store_cannot_run_the_same_department_twice(admin, deli_balbriggan):
    response = client_for(admin).post(
        BRANCH_LIST_URL, {"department_slug": "deli", "store_slug": "balbriggan"}, format="json"
    )
    assert response.status_code == 400
    assert "already runs" in str(response.data)


@pytest.mark.parametrize("actor", ["staff", "manager"])
def test_only_admins_may_remove_a_department_from_a_store(actor, request, deli_skerries):
    user = request.getfixturevalue(actor)
    response = client_for(user).delete(branch_url(deli_skerries.slug))
    assert response.status_code in (403, 404)
    assert StoreDepartment.objects.filter(pk=deli_skerries.pk).exists()


def test_admin_removes_a_department_from_a_store(admin, deli_skerries):
    assert client_for(admin).delete(branch_url(deli_skerries.slug)).status_code == 204
    assert not StoreDepartment.objects.filter(pk=deli_skerries.pk).exists()
    # The department still runs in the other two.
    assert StoreDepartment.objects.filter(department__slug="deli").count() == 2


def test_removing_a_department_from_a_store_is_refused_while_staff_are_in_it(
    admin, deli_balbriggan, staff
):
    response = client_for(admin).delete(branch_url(deli_balbriggan.slug))
    assert response.status_code == 400
    assert "still has 1 person assigned" in response.data["detail"]
    assert StoreDepartment.objects.filter(pk=deli_balbriggan.pk).exists()


def test_a_branch_cannot_be_moved_to_another_store(admin, deli_balbriggan):
    """Moving one would take its whole roster to a store they do not work in."""
    response = client_for(admin).patch(
        branch_url(deli_balbriggan.slug), {"store_slug": "skerries"}, format="json"
    )
    assert response.status_code == 200
    deli_balbriggan.refresh_from_db()
    assert deli_balbriggan.store.slug == "balbriggan"


def test_a_removed_department_cannot_be_assigned(admin, staff, deli_skerries):
    deli_skerries.delete()
    response = client_for(admin).patch(
        reverse("accounts:team-detail", args=[staff.pk]),
        {"department_slug": "deli-at-skerries", "store_slug": "skerries"},
        format="json",
    )
    assert response.status_code == 400


# ------------------------------------------------------------------ deleting


@pytest.mark.parametrize("actor", ["staff", "manager"])
def test_only_admins_may_delete_a_department(actor, request):
    user = request.getfixturevalue(actor)
    assert client_for(user).delete(detail_url("deli")).status_code == 403


def test_delete_is_refused_while_staff_are_assigned_anywhere(admin, staff, other_store_staff):
    """One person in any branch is enough to block the whole department."""
    response = client_for(admin).delete(detail_url("deli"))
    assert response.status_code == 400
    assert "still has 2 people assigned across the group" in response.data["detail"]
    assert Department.objects.filter(slug="deli").exists()


def test_empty_department_deletes_with_its_branches(admin, deli):
    assert client_for(admin).delete(detail_url("deli")).status_code == 204
    assert not StoreDepartment.objects.filter(department__slug="deli").exists()


def test_nested_department_on_a_user_names_its_store(manager, staff):
    rows = client_for(manager).get(reverse("accounts:team-list")).data["results"]
    member = next(entry for entry in rows if entry["email"] == staff.email)
    assert member["department"]["store"]["slug"] == "balbriggan"
    assert member["department"]["slug"] == "deli-at-balbriggan"
