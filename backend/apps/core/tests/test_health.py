from django.urls import reverse


def test_health_is_public_and_reports_db(client, db):
    response = client.get(reverse("core:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_schema_endpoint_is_reachable(client, db):
    response = client.get(reverse("schema"))
    assert response.status_code == 200
