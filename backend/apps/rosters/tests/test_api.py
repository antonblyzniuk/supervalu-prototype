"""Rosters: hours, breaks, what a week costs, and who may touch it."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.departments.models import StoreDepartment
from apps.rosters.models import Shift
from apps.stores.models import Store

User = get_user_model()
BOARD_URL = reverse("rosters:board")
SHIFT_URL = reverse("rosters:shift-list")

# A Sunday, so the trading week runs 2026-08-02 → 2026-08-08.
MONDAY = "2026-08-03"
TUESDAY = "2026-08-04"
WEEK_ANCHOR = "2026-08-05"


def shift_url(pk):
    return reverse("rosters:shift-detail", args=[pk])


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def balbriggan(db):
    return Store.objects.get(slug="balbriggan")


@pytest.fixture
def deli(balbriggan):
    return StoreDepartment.objects.get(department__slug="deli", store=balbriggan)


@pytest.fixture
def bakery(balbriggan):
    return StoreDepartment.objects.get(department__slug="bakery", store=balbriggan)


@pytest.fixture
def staff(deli, balbriggan):
    return User.objects.create_user(
        email="niamh@moriarty.ie",
        password="pw-12345678",
        first_name="Niamh",
        last_name="Walsh",
        store=balbriggan,
        department=deli,
        hourly_rate=Decimal("15.00"),
    )


@pytest.fixture
def unpaid_staff(bakery, balbriggan):
    """No explicit rate — costed at the statutory minimum."""
    return User.objects.create_user(
        email="aoife@moriarty.ie",
        password="pw-12345678",
        first_name="Aoife",
        store=balbriggan,
        department=bakery,
    )


@pytest.fixture
def manager(balbriggan):
    return User.objects.create_user(
        email="manager@moriarty.ie",
        password="pw-12345678",
        role=User.Role.MANAGER,
        store=balbriggan,
    )


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(email="admin@moriarty.ie", password="pw-12345678")


def roster(client, user, date=MONDAY, start="08:00", end="17:00", **extra):
    payload = {
        "user_id": user.pk,
        "date": date,
        "start_time": start,
        "end_time": end,
        **extra,
    }
    return client.post(SHIFT_URL, payload, format="json")


# ------------------------------------------------------------------ the hours


def test_a_nine_to_five_is_nine_hours(manager, staff):
    response = roster(client_for(manager), staff)
    assert response.status_code == 201, response.data
    assert response.data["duration_minutes"] == 540
    assert response.data["paid_minutes"] == 540
    assert response.data["hours"] == "9.00"
    assert response.data["cost"] == "135.00"  # 9 × 15.00


def test_an_unpaid_break_comes_off_the_paid_hours(manager, staff):
    response = roster(client_for(manager), staff, break_minutes=60)
    assert response.status_code == 201, response.data
    assert response.data["duration_minutes"] == 540
    assert response.data["paid_minutes"] == 480
    assert response.data["hours"] == "8.00"
    assert response.data["cost"] == "120.00"


def test_a_paid_break_stays_inside_the_paid_hours(manager, staff):
    response = roster(client_for(manager), staff, break_minutes=60, break_paid=True)
    assert response.status_code == 201, response.data
    assert response.data["paid_minutes"] == 540
    assert response.data["hours"] == "9.00"
    assert response.data["cost"] == "135.00"


def test_a_shift_over_midnight_is_not_negative(manager, staff):
    response = roster(client_for(manager), staff, start="22:00", end="02:00")
    assert response.status_code == 201, response.data
    assert response.data["duration_minutes"] == 240
    assert response.data["hours"] == "4.00"


def test_part_hours_are_costed_to_the_penny(manager, staff):
    # 08:00–12:20 is 4h20m; 4.3333h × 15.00 = 65.00
    response = roster(client_for(manager), staff, end="12:20")
    assert response.data["paid_minutes"] == 260
    assert response.data["hours"] == "4.33"
    assert response.data["cost"] == "65.00"


def test_somebody_with_no_rate_is_costed_at_the_minimum_wage(manager, unpaid_staff, settings):
    response = roster(client_for(manager), unpaid_staff)
    assert response.status_code == 201, response.data
    assert response.data["hourly_rate"] == str(settings.MINIMUM_HOURLY_RATE)
    assert response.data["cost"] == "127.80"  # 9 × 14.20


# ------------------------------------------------------------------ the rules


def test_a_shift_cannot_start_and_finish_at_the_same_time(manager, staff):
    response = roster(client_for(manager), staff, start="09:00", end="09:00")
    assert response.status_code == 400
    assert "end_time" in response.data


def test_an_unpaid_break_cannot_swallow_the_whole_shift(manager, staff):
    response = roster(client_for(manager), staff, start="09:00", end="12:00", break_minutes=180)
    assert response.status_code == 400
    assert "break_minutes" in response.data


def test_nobody_is_rostered_twice_on_one_day(manager, staff):
    client = client_for(manager)
    assert roster(client, staff).status_code == 201
    response = roster(client, staff, start="18:00", end="20:00")
    assert response.status_code == 400
    assert "already rostered" in str(response.data["date"])


def test_somebody_with_no_store_cannot_be_rostered(manager, deli):
    homeless = User.objects.create_user(email="nowhere@moriarty.ie", password="pw-12345678")
    response = roster(client_for(manager), homeless)
    assert response.status_code == 400
    assert "no store" in str(response.data["user_id"])


def test_a_shift_is_filed_against_the_persons_own_store(manager, staff, balbriggan):
    roster(client_for(manager), staff)
    assert Shift.objects.get().store == balbriggan


def test_editing_a_shift_recalculates_it(manager, staff):
    client = client_for(manager)
    created = roster(client, staff)
    response = client.patch(
        shift_url(created.data["id"]), {"end_time": "13:00"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["hours"] == "5.00"
    assert response.data["cost"] == "75.00"


def test_removing_a_shift_clears_the_day(manager, staff):
    client = client_for(manager)
    created = roster(client, staff)
    assert client.delete(shift_url(created.data["id"])).status_code == 204
    assert not Shift.objects.exists()


# ------------------------------------------------------------------- who sees


def test_anonymous_is_refused():
    assert APIClient().get(BOARD_URL, {"store": "balbriggan"}).status_code == 401


def test_staff_cannot_reach_the_roster(staff):
    """Rosters carry what everybody is paid, so they are management only."""
    client = client_for(staff)
    assert client.get(BOARD_URL, {"store": "balbriggan"}).status_code == 403
    assert roster(client, staff).status_code == 403


def test_a_manager_can_roster_any_store(manager, staff):
    assert roster(client_for(manager), staff).status_code == 201


# ------------------------------------------------------------------ the board


def test_the_board_names_the_trading_week(manager):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR})
    assert response.status_code == 200
    assert response.data["week_start"] == "2026-08-02"  # Sunday
    assert response.data["week_end"] == "2026-08-08"  # Saturday
    assert len(response.data["days"]) == 7


def test_the_board_needs_a_store(manager):
    assert client_for(manager).get(BOARD_URL).status_code == 400


def test_the_board_404s_for_a_store_that_does_not_exist(manager):
    assert client_for(manager).get(BOARD_URL, {"store": "nowhere"}).status_code == 404


def test_the_board_lists_every_department_the_store_runs(manager, staff, balbriggan):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    # The trailing "No department" group is asserted separately below.
    names = [group["name"] for group in response.data["departments"] if group["slug"]]
    assert names == sorted(
        StoreDepartment.objects.filter(store=balbriggan).values_list(
            "department__name", flat=True
        )
    )


def test_the_board_lists_people_under_their_department(manager, staff, unpaid_staff):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    by_name = {group["name"]: group for group in response.data["departments"]}
    assert [p["person"]["email"] for p in by_name["Deli"]["people"]] == [staff.email]
    assert [p["person"]["email"] for p in by_name["Bakery"]["people"]] == [unpaid_staff.email]


def test_the_board_includes_managers(manager):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    everyone = [
        person["person"]["email"]
        for group in response.data["departments"]
        for person in group["people"]
    ]
    assert manager.email in everyone


def test_somebody_with_no_department_is_grouped_last(manager, staff, balbriggan):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    last = response.data["departments"][-1]
    # The manager fixture has a store but no department.
    assert last["name"] == "No department at this store"
    assert [p["person"]["email"] for p in last["people"]] == [manager.email]


def test_unrostered_people_still_appear_with_a_zero_week(manager, staff):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    deli = next(g for g in response.data["departments"] if g["name"] == "Deli")
    person = deli["people"][0]
    assert person["shifts"] == []
    assert person["totals"] == {
        "shift_count": 0,
        "paid_minutes": 0,
        "hours": "0.00",
        "cost": "0.00",
    }


def test_the_board_adds_a_week_up_per_person_department_and_store(
    manager, staff, unpaid_staff
):
    client = client_for(manager)
    roster(client, staff, date=MONDAY, break_minutes=60)  # 8h × 15.00 = 120.00
    roster(client, staff, date=TUESDAY, break_minutes=60)  # 8h × 15.00 = 120.00
    roster(client, unpaid_staff, date=MONDAY)  # 9h × 14.20 = 127.80

    response = client.get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR})
    groups = {group["name"]: group for group in response.data["departments"]}

    niamh = groups["Deli"]["people"][0]
    assert niamh["totals"]["hours"] == "16.00"
    assert niamh["totals"]["cost"] == "240.00"
    assert groups["Deli"]["totals"]["cost"] == "240.00"

    aoife = groups["Bakery"]["people"][0]
    assert aoife["totals"]["hours"] == "9.00"
    assert aoife["totals"]["cost"] == "127.80"

    assert response.data["totals"]["hours"] == "25.00"
    assert response.data["totals"]["cost"] == "367.80"
    assert response.data["totals"]["shift_count"] == 3
    assert response.data["totals"]["people_rostered"] == 2


def test_the_board_only_counts_the_week_asked_for(manager, staff):
    client = client_for(manager)
    roster(client, staff, date=MONDAY)  # inside the week
    roster(client, staff, date="2026-08-10")  # the following Monday

    response = client.get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR})
    assert response.data["totals"]["shift_count"] == 1


def test_the_board_leaves_other_stores_alone(manager, staff):
    """Skerries' roster must not pick up a Balbriggan shift."""
    roster(client_for(manager), staff)
    response = client_for(manager).get(BOARD_URL, {"store": "skerries"})
    assert response.data["totals"]["shift_count"] == 0


def test_deactivated_people_drop_off_the_board(manager, staff):
    staff.is_active = False
    staff.save(update_fields=["is_active"])
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    everyone = [
        person["person"]["email"]
        for group in response.data["departments"]
        for person in group["people"]
    ]
    assert staff.email not in everyone


def test_a_deactivated_person_still_holding_shifts_stays_visible(manager, staff):
    """Otherwise the store total counts hours against a row nobody can see."""
    roster(client_for(manager), staff, break_minutes=60)
    staff.is_active = False
    staff.save(update_fields=["is_active"])

    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR})
    rows = [
        person
        for group in response.data["departments"]
        for person in group["people"]
        if person["person"]["email"] == staff.email
    ]
    assert len(rows) == 1
    assert rows[0]["person"]["is_active"] is False
    assert rows[0]["totals"]["hours"] == "8.00"
    assert response.data["totals"]["hours"] == "8.00"


def test_somebody_who_transferred_still_reconciles(manager, staff, deli):
    """Their shift stays with the store it was worked at, so their row must too."""
    roster(client_for(manager), staff, break_minutes=60)
    skerries = Store.objects.get(slug="skerries")
    staff.store = skerries
    staff.department = StoreDepartment.objects.get(
        department__slug="deli", store=skerries
    )
    staff.save(update_fields=["store", "department"])

    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR})
    trailing = response.data["departments"][-1]
    assert trailing["name"] == "No department at this store"
    # Alongside the manager, who simply has no department.
    assert staff.email in [p["person"]["email"] for p in trailing["people"]]

    # The visible rows add up to the store total.
    from_rows = sum(
        person["totals"]["paid_minutes"]
        for group in response.data["departments"]
        for person in group["people"]
    )
    assert from_rows == response.data["totals"]["paid_minutes"] == 480


# -------------------------------------------------------------------- the pay


def test_the_board_flags_a_rate_nobody_has_set(manager, staff, unpaid_staff, settings):
    response = client_for(manager).get(BOARD_URL, {"store": "balbriggan"})
    groups = {group["name"]: group for group in response.data["departments"]}

    niamh = groups["Deli"]["people"][0]["person"]
    assert niamh["hourly_rate"] == "15.00"
    assert niamh["rate_is_default"] is False

    aoife = groups["Bakery"]["people"][0]["person"]
    assert aoife["hourly_rate"] == str(settings.MINIMUM_HOURLY_RATE)
    assert aoife["rate_is_default"] is True


def test_only_an_admin_sets_what_somebody_is_paid(manager, admin, staff):
    url = reverse("accounts:team-detail", args=[staff.pk])

    refused = client_for(manager).patch(url, {"hourly_rate": "20.00"}, format="json")
    assert refused.status_code == 400
    assert "admin" in str(refused.data["hourly_rate"]).lower()

    allowed = client_for(admin).patch(url, {"hourly_rate": "20.00"}, format="json")
    assert allowed.status_code == 200
    staff.refresh_from_db()
    assert staff.hourly_rate == Decimal("20.00")


def test_nobody_is_paid_below_the_minimum_wage(admin, staff, settings):
    url = reverse("accounts:team-detail", args=[staff.pk])
    response = client_for(admin).patch(url, {"hourly_rate": "5.00"}, format="json")
    assert response.status_code == 400
    assert str(settings.MINIMUM_HOURLY_RATE) in str(response.data["hourly_rate"])


def test_clearing_a_rate_falls_back_to_the_minimum_wage(admin, staff, settings):
    url = reverse("accounts:team-detail", args=[staff.pk])
    assert client_for(admin).patch(url, {"hourly_rate": None}, format="json").status_code == 200

    staff.refresh_from_db()
    assert staff.hourly_rate is None
    assert staff.effective_hourly_rate == settings.MINIMUM_HOURLY_RATE


# ------------------------------------------------------------------ exporting

EXPORT_URL = reverse("rosters:export")


def test_staff_cannot_export_a_roster(staff):
    assert client_for(staff).get(EXPORT_URL, {"store": "balbriggan"}).status_code == 403


def test_export_needs_a_store(manager):
    assert client_for(manager).get(EXPORT_URL).status_code == 400


def test_export_refuses_an_unknown_output(manager):
    response = client_for(manager).get(
        EXPORT_URL, {"store": "balbriggan", "output": "csv"}
    )
    assert response.status_code == 400


def test_export_renders_a_pdf(manager, staff, unpaid_staff):
    client = client_for(manager)
    roster(client, staff, break_minutes=60)
    roster(client, unpaid_staff)

    response = client.get(
        EXPORT_URL, {"store": "balbriggan", "week": WEEK_ANCHOR, "output": "pdf"}
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "attachment; filename=" in response["Content-Disposition"]

    body = b"".join(response.streaming_content) if response.streaming else response.content
    assert body.startswith(b"%PDF-")
    assert len(body) > 1000


def test_export_can_be_narrowed_to_one_department(manager, staff, unpaid_staff):
    client = client_for(manager)
    roster(client, staff, break_minutes=60)  # Deli, 8h × 15.00 = 120.00
    roster(client, unpaid_staff)  # Bakery, 9h × 14.20 = 127.80

    response = client.get(
        EXPORT_URL,
        {"store": "balbriggan", "week": WEEK_ANCHOR, "department": "deli", "output": "json"},
    )
    assert response.status_code == 200
    assert [group["name"] for group in response.data["departments"]] == ["Deli"]
    # Totals describe exactly what was asked for, not the whole store.
    assert response.data["totals"]["cost"] == "120.00"
    assert response.data["totals"]["hours"] == "8.00"
    assert "Deli" in response.data["subtitle"]


def test_export_accepts_several_departments(manager, staff, unpaid_staff):
    client = client_for(manager)
    roster(client, staff, break_minutes=60)
    roster(client, unpaid_staff)

    response = client.get(
        EXPORT_URL,
        {
            "store": "balbriggan",
            "week": WEEK_ANCHOR,
            "department": "deli,bakery",
            "output": "json",
        },
    )
    assert sorted(group["name"] for group in response.data["departments"]) == ["Bakery", "Deli"]
    assert response.data["totals"]["cost"] == "247.80"  # 120.00 + 127.80


def test_a_narrowed_export_leaves_out_people_with_no_department(manager, staff):
    """The manager fixture has no department, so a Deli export must skip them."""
    response = client_for(manager).get(
        EXPORT_URL, {"store": "balbriggan", "department": "deli", "output": "json"}
    )
    everyone = [
        person["person"]["email"]
        for group in response.data["departments"]
        for person in group["people"]
    ]
    assert staff.email in everyone
    assert manager.email not in everyone


def test_export_matches_the_board_it_was_taken_from(manager, staff, unpaid_staff):
    client = client_for(manager)
    roster(client, staff, break_minutes=60)
    roster(client, unpaid_staff)

    board = client.get(BOARD_URL, {"store": "balbriggan", "week": WEEK_ANCHOR}).data
    export = client.get(
        EXPORT_URL, {"store": "balbriggan", "week": WEEK_ANCHOR, "output": "json"}
    ).data
    assert export["totals"] == board["totals"]
    assert [g["name"] for g in export["departments"]] == [g["name"] for g in board["departments"]]


def test_exporting_an_empty_week_still_renders(manager):
    response = client_for(manager).get(
        EXPORT_URL, {"store": "skerries", "week": WEEK_ANCHOR, "output": "pdf"}
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_export_refuses_a_department_the_store_does_not_run(manager):
    response = client_for(manager).get(
        EXPORT_URL, {"store": "balbriggan", "department": "fishmonger", "output": "json"}
    )
    assert response.status_code == 400
    assert "does not run" in str(response.data["department"])


def test_export_refuses_a_branch_slug(manager, deli):
    """The board's `slug` names the branch; the export wants the department.

    Passing the wrong one used to produce a valid-looking export of nobody.
    """
    response = client_for(manager).get(
        EXPORT_URL,
        {"store": "balbriggan", "department": deli.slug, "output": "json"},
    )
    assert response.status_code == 400
    assert "deli-at-balbriggan" in str(response.data["department"])


def test_a_department_export_carries_that_departments_people(manager, staff):
    """Guards the slug the PDF button sends: `department_slug`, not `slug`."""
    board = client_for(manager).get(BOARD_URL, {"store": "balbriggan"}).data
    deli_group = next(g for g in board["departments"] if g["name"] == "Deli")

    response = client_for(manager).get(
        EXPORT_URL,
        {"store": "balbriggan", "department": deli_group["department_slug"], "output": "json"},
    )
    assert response.status_code == 200
    assert [g["name"] for g in response.data["departments"]] == ["Deli"]
    assert [p["person"]["email"] for p in response.data["departments"][0]["people"]] == [
        staff.email
    ]
