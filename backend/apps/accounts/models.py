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
    phone = models.CharField(max_length=32, blank=True)

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
