from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.core.permissions import IsAdminOrReadOnly, IsManagerReadAdminWrite

from .models import Department, StoreDepartment
from .serializers import (
    DepartmentDetailSerializer,
    DepartmentSerializer,
    StoreDepartmentDetailSerializer,
    StoreDepartmentSerializer,
)


def member_prefetch():
    """Rosters, ordered as the team page orders them."""
    return Prefetch("members", queryset=User.objects.select_related("store").order_by("email"))


class DepartmentViewSet(viewsets.ModelViewSet):
    """Department kinds — "the Deli in general", pooled across every branch.

    Manager/admin only, because pooling is exactly what a staff user must not
    see: they are scoped to one branch of one department, which they read
    through `StoreDepartmentViewSet` instead. Writes are admin only.
    """

    permission_classes = (IsManagerReadAdminWrite,)
    serializer_class = DepartmentSerializer
    lookup_field = "slug"
    # A dozen-odd rows of reference data — the pickers want the whole list.
    pagination_class = None
    filterset_fields = ("is_active",)
    search_fields = ("name", "code", "description")
    ordering_fields = ("name", "member_count", "store_count", "created_at")
    ordering = ("name",)

    def get_queryset(self):
        queryset = Department.objects.annotate(
            member_count=Count(
                "store_departments__members",
                filter=Q(store_departments__members__is_active=True),
                distinct=True,
            ),
            store_count=Count("store_departments", distinct=True),
        )
        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "store_departments",
                    queryset=StoreDepartment.objects.select_related(
                        "store", "manager", "manager__store"
                    ).prefetch_related(member_prefetch()),
                )
            )
        return queryset

    def get_serializer_class(self):
        return DepartmentDetailSerializer if self.action == "retrieve" else DepartmentSerializer

    def perform_destroy(self, instance):
        """Refuse to orphan staff — every colleague belongs to a department.

        Deleting the kind cascades to its branches, so the check has to span all
        of them rather than any single store.
        """
        assigned = User.objects.filter(department__department=instance).count()
        if assigned:
            raise ValidationError(
                {
                    "detail": (
                        f"{instance.name} still has {assigned} "
                        f"{'person' if assigned == 1 else 'people'} assigned across the "
                        "group. Move them to another department first, or set this one to "
                        "archived instead."
                    )
                }
            )
        try:
            instance.delete()
        except ProtectedError:
            # Belt and braces: somebody was assigned between the count and the
            # delete. A 400 with a usable message beats a 500.
            raise ValidationError(
                {"detail": f"{instance.name} still has staff assigned and cannot be deleted."}
            ) from None


class StoreDepartmentViewSet(viewsets.ModelViewSet):
    """A department in one branch — "Deli · Balbriggan", and its roster.

    Scoping is the whole point of this endpoint: a staff user sees the one they
    are in and nothing else, not other departments in their store and not the
    same department in another store. Managers and admins see every branch;
    only admins can add, edit or remove one.

    Adding and removing rows here is how a store's set of departments is
    managed — not every branch runs every department.
    """

    permission_classes = (IsAdminOrReadOnly,)
    serializer_class = StoreDepartmentSerializer
    lookup_field = "slug"
    pagination_class = None
    filterset_fields = {
        "store__slug": ["exact"],
        "department__slug": ["exact"],
    }
    search_fields = ("department__name", "department__code", "store__name")
    ordering_fields = ("department__name", "store__name")
    ordering = ("department__name", "store__name")

    def get_queryset(self):
        queryset = (
            StoreDepartment.objects.select_related(
                "department", "store", "manager", "manager__store"
            )
            .prefetch_related(member_prefetch())
        )

        user = self.request.user
        if user.is_manager:
            return queryset
        # Staff see their own department only. Nobody assigned yet sees nothing,
        # the same way an unassigned store shows no dockets.
        if user.department_id:
            return queryset.filter(pk=user.department_id)
        return queryset.none()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StoreDepartmentDetailSerializer
        return StoreDepartmentSerializer

    def perform_destroy(self, instance):
        """Closing a department in a store must not orphan its staff."""
        assigned = instance.members.count()
        if assigned:
            raise ValidationError(
                {
                    "detail": (
                        f"{instance} still has {assigned} "
                        f"{'person' if assigned == 1 else 'people'} assigned. Move them to "
                        "another department in this store first."
                    )
                }
            )
        try:
            instance.delete()
        except ProtectedError:
            # Belt and braces: somebody was assigned between the count and the
            # delete. A 400 with a usable message beats a 500.
            raise ValidationError(
                {"detail": f"{instance} still has staff assigned and cannot be removed."}
            ) from None
