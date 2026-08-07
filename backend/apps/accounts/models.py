from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """Manager for a user model that authenticates by email instead of username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        # Fully lower-cased, not just the domain as `normalize_email` does:
        # email is the login field, and staff type their address inconsistently.
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Store employee account.

    `username` is dropped in favour of email login. `role` drives coarse
    in-app permissions; Django groups/permissions stay available for anything
    finer grained.
    """

    class Role(models.TextChoices):
        STAFF = "staff", _("Staff")
        MANAGER = "manager", _("Manager")
        ADMIN = "admin", _("Admin")

    username = None
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)
    employee_id = models.CharField(max_length=32, blank=True)
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text=_("Home store — pre-selected on new dockets."),
    )
    department = models.ForeignKey(
        "departments.StoreDepartment",
        # PROTECT, not SET_NULL: everyone belongs to a department, so one with
        # staff in it has to be emptied before it can go.
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
        help_text=_("Department they work in, at their store. Implies the store."),
    )
    phone = models.CharField(max_length=32, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Euro per hour. Blank means the national minimum wage."),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ("email",)

    def __str__(self):
        return self.email

    @property
    def is_manager(self):
        return self.role in {self.Role.MANAGER, self.Role.ADMIN}

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def effective_hourly_rate(self):
        """What an hour of this person's time costs.

        Nobody is paid below the statutory minimum, so an account without an
        explicit rate is costed at it rather than at zero — a roster that
        silently valued somebody at nothing would be worse than useless.
        """
        return self.hourly_rate if self.hourly_rate is not None else settings.MINIMUM_HOURLY_RATE
