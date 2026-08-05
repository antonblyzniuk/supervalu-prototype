from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsManager

from .models import User
from .serializers import (
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    UserSerializer,
)


class MeView(generics.RetrieveAPIView):
    """Return the profile of the authenticated user."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TeamViewSet(viewsets.ModelViewSet):
    """Staff administration for managers and admins.

    Assigning someone a store is what scopes their access: a `staff` user only
    ever sees dockets for the store set here.
    """

    permission_classes = (IsManager,)
    queryset = User.objects.select_related("store").order_by("email")
    filterset_fields = ("role", "is_active", "store__slug")
    search_fields = ("email", "first_name", "last_name", "employee_id")
    ordering_fields = ("email", "role", "date_joined", "last_login")

    def get_serializer_class(self):
        return TeamMemberCreateSerializer if self.action == "create" else TeamMemberSerializer

    def perform_destroy(self, instance):
        """Deactivate rather than delete — dockets keep pointing at the filer."""
        if instance.pk == self.request.user.pk:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"detail": "You cannot deactivate your own account."})
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @extend_schema(
        request={"application/json": {"type": "object", "properties": {"password": {}}}},
        responses={200: dict},
        summary="Set a colleague's password",
    )
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        """Reset a password for someone who is locked out.

        The manager hands the new password over in person; there is no email
        delivery in the prototype.
        """
        user = self.get_object()
        password = request.data.get("password") or ""

        if user.role == User.Role.ADMIN and request.user.role != User.Role.ADMIN:
            return Response(
                {"detail": "Only an admin can reset an admin's password."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"detail": f"Password updated for {user.email}."})
