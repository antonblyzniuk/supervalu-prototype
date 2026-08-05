from rest_framework import status
from rest_framework.exceptions import APIException


class StorageUnavailable(APIException):
    """Raised when an upload cannot be written to disk.

    A misconfigured media volume is an operational fault, not a bad request,
    so it gets a 503 and a message that names the actual cause instead of an
    opaque 500.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "Uploads cannot be saved right now — the server's file storage is not "
        "writable. The docket was not saved. Please tell whoever manages the "
        "deployment; see /api/health/ for detail."
    )
    default_code = "storage_unavailable"
