import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.core.permissions import IsManager

from .models import User
from .serializers import (
    AdminBootstrapSerializer,
    TeamMemberCreateSerializer,
    TeamMemberSerializer,
    UserSerializer,
)


class MeView(generics.RetrieveAPIView):
    """Return the profile of the authenticated user."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


logger = logging.getLogger(__name__)


class AdminBootstrapView(generics.CreateAPIView):
    """Create an admin account by presenting the shared setup code.

    Exists so the first admin can be created without shell access. Disabled
    entirely unless ADMIN_BOOTSTRAP_CODE is set, so unsetting that variable
    once the office is up and running closes the door.
    """

    serializer_class = AdminBootstrapSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = "admin_bootstrap"

    @extend_schema(
        summary="Create an admin account with the shared setup code",
        responses={201: UserSerializer, 400: None, 404: None},
    )
    def post(self, request, *args, **kwargs):
        if not settings.ADMIN_BOOTSTRAP_CODE:
            # 404 rather than 403: an endpoint that is switched off should not
            # advertise that it exists.
            raise Http404

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "Admin bootstrap rejected from %s: %s",
                request.META.get("REMOTE_ADDR", "unknown"),
                ", ".join(serializer.errors),
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        logger.info("Admin account %s created via bootstrap endpoint.", user.email)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class TeamViewSet(viewsets.ModelViewSet):
    """Staff administration for managers and admins.

    Assigning someone a store is what scopes their access: a `staff` user only
    ever sees dockets for the store set here.
    """

    permission_classes = (IsManager,)
    queryset = User.objects.select_related(
        "store", "department", "department__department", "department__store"
    ).order_by("email")
    # `department__slug` narrows to one branch ("Deli · Balbriggan");
    # `department__department__slug` to a department across every branch.
    filterset_fields = (
        "role",
        "is_active",
        "store__slug",
        "department__slug",
        "department__department__slug",
    )
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
