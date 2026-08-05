"""Edge cases that reach the docket API from real use or a broken deployment."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.dockets.models import Docket
from apps.dockets.serializers import MAX_LINES, MAX_PHOTOS

from .conftest import PNG_DATA_URL

LIST_URL = reverse("dockets:docket-list")


# --------------------------------------------------------------- amounts


@pytest.mark.parametrize("bad", ["abc", "1.2.3", "NaN", "Infinity", "--5", "1e999"])
def test_non_numeric_amounts_are_rejected(api, ambient_payload, bad):
    ambient_payload["lines"][0]["amounts"] = {"groc": bad}
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400, f"{bad!r} should not be accepted"
    assert not Docket.objects.exists()


def test_absurdly_large_amount_is_rejected_not_a_500(api, ambient_payload):
    ambient_payload["lines"][0]["amounts"] = {"groc": "99999999999999"}
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400


def test_amounts_accept_thousands_separators_and_whitespace(api, ambient_payload):
    ambient_payload["lines"] = [
        {"position": 0, "amounts": {"groc": " 1,250.50 "}, "total": "0"}
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201, response.data
    assert Docket.objects.get().total == Decimal("1250.50")


def test_negative_amounts_are_allowed_for_credits(api, ambient_payload):
    ambient_payload["lines"] = [{"position": 0, "amounts": {"groc": "-40.00"}, "total": "0"}]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201
    assert Docket.objects.get().total == Decimal("-40.00")


def test_line_total_is_derived_not_trusted(api, ambient_payload):
    """A client claiming a total that contradicts its columns is corrected."""
    ambient_payload["lines"] = [
        {"position": 0, "amounts": {"groc": "10.00", "wine": "5.00"}, "total": "999999.00"}
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201
    assert Docket.objects.get().total == Decimal("15.00")
    assert response.data["lines"][0]["total"] == "15.00"


def test_blank_amount_values_are_dropped(api, ambient_payload):
    ambient_payload["lines"] = [
        {"position": 0, "amounts": {"groc": "12.00", "wine": "", "cigs": None}, "total": "0"}
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201
    assert response.data["lines"][0]["amounts"] == {"groc": "12.00"}


# ----------------------------------------------------------------- lines


def test_empty_line_list_is_rejected(api, ambient_payload):
    ambient_payload["lines"] = []
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "lines" in response.data


def test_too_many_lines_are_rejected(api, ambient_payload):
    ambient_payload["lines"] = [
        {"position": i, "amounts": {"groc": "1.00"}, "total": "1.00"}
        for i in range(MAX_LINES + 1)
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "lines" in response.data


def test_a_docket_at_the_line_limit_is_accepted(api, ambient_payload):
    ambient_payload["lines"] = [
        {"position": i, "amounts": {"groc": "1.00"}, "total": "1.00"} for i in range(MAX_LINES)
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201
    assert Docket.objects.get().lines.count() == MAX_LINES


def test_too_many_photos_are_rejected(api, ambient_payload):
    ambient_payload["photos"] = [{"image": PNG_DATA_URL} for _ in range(MAX_PHOTOS + 1)]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "photos" in response.data


# ------------------------------------------------------------ references


def test_unknown_store_slug_is_a_400_not_a_crash(manager_api, ambient_payload):
    ambient_payload["store"] = "does-not-exist"
    response = manager_api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "store" in response.data


def test_malformed_date_is_a_400(api, ambient_payload):
    ambient_payload["week_ending"] = "not-a-date"
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400


def test_unknown_docket_type_is_a_400(api, ambient_payload):
    ambient_payload["docket_type"] = "seafood"
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400


def test_duplicate_signature_roles_are_rejected(api, ambient_payload):
    ambient_payload["signatures"] = [
        {"role": "manager", "image": PNG_DATA_URL},
        {"role": "manager", "image": PNG_DATA_URL},
    ]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert "signatures" in response.data


def test_signature_role_from_another_type_is_rejected(api, ambient_payload):
    ambient_payload["signatures"] = [{"role": "incoming_manager", "image": PNG_DATA_URL}]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400


@pytest.mark.parametrize(
    "bad_image",
    [
        "not-a-data-url",
        "data:text/plain;base64,aGVsbG8=",
        "data:image/png;base64,!!!not-base64!!!",
        "data:image/png;base64,",
    ],
)
def test_malformed_signature_images_are_rejected(api, ambient_payload, bad_image):
    ambient_payload["signatures"] = [{"role": "manager", "image": bad_image}]
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 400
    assert not Docket.objects.exists()


# --------------------------------------------------------------- storage


@pytest.fixture
def broken_media_root(settings, tmp_path):
    """A MEDIA_ROOT that cannot be created, whatever user the tests run as.

    Permission bits are no good here — CI and the container both run as root,
    which ignores them. Rooting the media path underneath a regular file makes
    mkdir fail with NotADirectoryError for everyone, which is the same OSError
    family a missing or read-only volume produces.
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("this is a file, not a directory")
    settings.MEDIA_ROOT = str(blocker / "media")
    return settings.MEDIA_ROOT


def test_unwritable_media_root_gives_503_not_500(api, ambient_payload, broken_media_root):
    """A missing or root-owned volume must not look like an app crash."""
    ambient_payload["signatures"] = [{"role": "manager", "image": PNG_DATA_URL}]
    response = api.post(LIST_URL, ambient_payload, format="json")

    assert response.status_code == 503
    assert "storage" in str(response.data["detail"]).lower()
    # The whole save is rolled back, so no half-written docket is left behind.
    assert not Docket.objects.exists()


def test_docket_without_uploads_works_even_if_media_is_broken(
    api, ambient_payload, broken_media_root
):
    ambient_payload.pop("signatures", None)
    ambient_payload.pop("photos", None)
    response = api.post(LIST_URL, ambient_payload, format="json")
    assert response.status_code == 201


def test_health_reports_broken_media_but_stays_up(api, broken_media_root, db):
    response = api.get(reverse("core:health"))
    assert response.status_code == 200  # the app still works; only uploads don't
    assert response.data["database"] == "ok"
    assert "not writable" in response.data["media"]
    assert response.data["status"] == "error"


# ---------------------------------------------------------------- update


def test_updating_without_lines_key_keeps_existing_lines(api, ambient_payload):
    created = api.post(LIST_URL, ambient_payload, format="json").data
    url = reverse("dockets:docket-detail", args=[created["id"]])

    response = api.patch(url, {"reference": "updated-ref"}, format="json")
    assert response.status_code == 200
    assert len(response.data["lines"]) == 2
    assert response.data["reference"] == "updated-ref"


def test_update_cannot_empty_the_line_list(api, ambient_payload):
    created = api.post(LIST_URL, ambient_payload, format="json").data
    url = reverse("dockets:docket-detail", args=[created["id"]])

    response = api.patch(url, {"lines": []}, format="json")
    assert response.status_code == 400


def test_fetching_a_missing_docket_is_a_404(api, db):
    url = reverse("dockets:docket-detail", args=["00000000-0000-0000-0000-000000000000"])
    assert api.get(url).status_code == 404


def test_malformed_uuid_is_a_404_not_a_500(api, db):
    assert api.get("/api/dockets/not-a-uuid/").status_code == 404


# ------------------------------------------------------------- pdf export


def test_pdf_export_survives_a_missing_image_file(api, ambient_payload, tmp_path, settings):
    """Uploads lost to a wiped volume must not break every export."""
    settings.MEDIA_ROOT = str(tmp_path)
    ambient_payload["signatures"] = [{"role": "manager", "image": PNG_DATA_URL}]
    ambient_payload["photos"] = [{"image": PNG_DATA_URL}]
    created = api.post(LIST_URL, ambient_payload, format="json")
    assert created.status_code == 201

    # Delete the files behind the records, exactly as a redeploy would.
    for path in tmp_path.rglob("*.png"):
        path.unlink()

    response = api.get(reverse("dockets:docket-export"), {"output": "pdf"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_pdf_export_with_no_dockets_still_renders(api, db):
    response = api.get(reverse("dockets:docket-export"), {"output": "pdf"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
