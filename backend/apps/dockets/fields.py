import base64
import binascii
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers

DATA_URL_PREFIX = "data:"
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class Base64ImageField(serializers.ImageField):
    """Accepts a `data:image/...;base64,...` string as well as a normal upload.

    Signature pads and phone camera previews both produce data URLs, and the
    frontend posts a docket as one JSON document, so this is the ingest path.
    Reads still return the stored file URL.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith(DATA_URL_PREFIX):
            header, _, payload = data.partition(",")
            if not payload:
                raise serializers.ValidationError("Malformed data URL.")
            mime = header[len(DATA_URL_PREFIX) :].split(";")[0]
            if not mime.startswith("image/"):
                raise serializers.ValidationError("Only image data URLs are accepted.")
            try:
                decoded = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise serializers.ValidationError("Could not decode base64 image.") from exc
            if len(decoded) > MAX_IMAGE_BYTES:
                raise serializers.ValidationError("Image is larger than 8 MB.")
            extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(
                mime, "png"
            )
            data = ContentFile(decoded, name=f"{uuid.uuid4().hex}.{extension}")
        return super().to_internal_value(data)

    def to_representation(self, value):
        """Return a root-relative URL, not an absolute one.

        DRF would build the URL from the request Host, which behind the Vite
        dev proxy (and any reverse proxy) is the internal service name — a URL
        the browser cannot resolve. `/media/...` always works.
        """
        if not value:
            return None
        return value.url
