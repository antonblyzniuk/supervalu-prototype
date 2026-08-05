import contextlib
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def check_database():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # noqa: BLE001 - any DB failure means unhealthy
        return False, str(exc)
    return True, "ok"


def check_media_storage():
    """Prove we can actually write an upload, not just that a path is set.

    Signature and photo saves are the one thing that touches the filesystem,
    and a missing or root-owned volume mount is invisible until someone tries
    to file a docket. Writing a probe file here makes it visible up front.
    """
    root = Path(settings.MEDIA_ROOT)
    probe = root / f".healthcheck-{uuid.uuid4().hex}"
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe.write_bytes(b"ok")
    except OSError as exc:
        return False, f"{root} is not writable: {exc}"
    finally:
        with contextlib.suppress(OSError):
            probe.unlink(missing_ok=True)
    return True, "ok"


def media_is_persistent():
    """Whether uploads survive a redeploy.

    Writable is not the same as durable: with no volume attached the container
    filesystem accepts writes happily and then throws them away on the next
    deploy. Railway exposes RAILWAY_VOLUME_MOUNT_PATH only when a volume is
    actually mounted, so that is the honest signal.
    """
    mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "")
    if not mount:
        # Not on Railway (local/compose) — treat a bind mount as persistent and
        # say nothing, since there is no platform signal to go on.
        return None if not os.environ.get("RAILWAY_ENVIRONMENT_NAME") else False
    try:
        return Path(settings.MEDIA_ROOT).resolve().is_relative_to(Path(mount).resolve())
    except (OSError, ValueError):
        return False


class HealthView(APIView):
    """Liveness/readiness probe — process, database, and upload storage."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        responses={200: {"type": "object"}, 503: {"type": "object"}},
        summary="Service health",
    )
    def get(self, request):
        database_ok, database_detail = check_database()
        media_ok, media_detail = check_media_storage()
        persistent = media_is_persistent()

        payload = {
            "status": "ok" if (database_ok and media_ok) else "error",
            "database": database_detail,
            "media": media_detail,
            "media_root": str(settings.MEDIA_ROOT),
        }

        if persistent is False:
            payload["media_persistent"] = False
            payload["media_warning"] = (
                "Uploads are being written to the container filesystem and will "
                "be lost on the next deploy. Attach a volume and point "
                "DJANGO_MEDIA_ROOT inside it."
            )
        elif persistent is True:
            payload["media_persistent"] = True

        # Media problems are reported but do not fail the probe: the rest of the
        # app still works, and failing here would take the whole service down
        # rather than degrading one feature.
        return Response(payload, status=200 if database_ok else 503)
