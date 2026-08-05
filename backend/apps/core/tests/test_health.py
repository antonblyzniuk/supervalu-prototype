from django.urls import reverse


def test_health_is_public_and_reports_db_and_storage(client, db):
    response = client.get(reverse("core:health"))
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    # Uploads are the one thing that touches disk, so the probe proves it can
    # write rather than just reporting a configured path.
    assert payload["media"] == "ok"
    assert payload["media_root"]


def test_health_flags_uploads_that_will_not_survive_a_deploy(client, db, settings, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)

    payload = client.get(reverse("core:health")).json()
    assert payload["media_persistent"] is False
    assert "lost on the next deploy" in payload["media_warning"]


def test_health_is_content_with_a_mounted_volume(client, db, settings, monkeypatch, tmp_path):
    volume = tmp_path / "data"
    (volume / "media").mkdir(parents=True)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(volume))
    settings.MEDIA_ROOT = str(volume / "media")

    payload = client.get(reverse("core:health")).json()
    assert payload["media_persistent"] is True
    assert "media_warning" not in payload


def test_schema_endpoint_is_reachable(client, db):
    response = client.get(reverse("schema"))
    assert response.status_code == 200
