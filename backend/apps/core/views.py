from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness/readiness probe — checks the process and its DB connection."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        responses={200: {"type": "object"}, 503: {"type": "object"}},
        summary="Service health",
    )
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:  # noqa: BLE001 - report any DB failure as unhealthy
            return Response({"status": "error", "database": str(exc)}, status=503)
        return Response({"status": "ok", "database": "ok"})
