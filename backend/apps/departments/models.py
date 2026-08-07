from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Department(TimeStampedModel):
    """A kind of trading department — Deli, Bakery, Off-licence and so on.

    Group-wide and abstract: nobody is assigned to a `Department` directly. It
    exists so "the Deli across the group" is one thing you can ask about, while
    the branch-level rosters live on `StoreDepartment`.

    Fields here are deliberately open ended — the detail screen renders whatever
    the serializer exposes, so adding a column shows up in the UI without a
    matching frontend change.
    """

    name = models.CharField(max_length=64, unique=True)
    # Filled in from the name on first save and then left alone, so renaming a
    # department does not break links people have bookmarked.
    slug = models.SlugField(max_length=64, unique=True, blank=True)
    code = models.CharField(max_length=16, blank=True, help_text="Optional internal code.")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = build_unique_slug(Department, slugify(self.name), self.pk)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "slug"}
        super().save(*args, **kwargs)


class StoreDepartment(TimeStampedModel):
    """One department as it exists in one branch — "Deli · Balbriggan".

    This is what staff are assigned to, which is why every roster is store
    specific and a staff user never sees another branch. Rolling the instances
    of one `department` back up is what answers "the Deli in general".

    A store runs a department or it does not, and that is the presence of a row
    here — there is no separate "closed" flag to keep in step with it. Removing
    one is refused while anybody is still assigned (`User.department` is
    PROTECT), so the staff move first.
    """

    department = models.ForeignKey(
        Department,
        # The kind is the parent record; closing it closes its branches. The
        # PROTECT on `User.department` is what stops that orphaning anybody.
        on_delete=models.CASCADE,
        related_name="store_departments",
    )
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="departments",
    )
    slug = models.SlugField(max_length=128, unique=True, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="store_departments_led",
        help_text="Head of department in this branch.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("department__name", "store__name")
        constraints = [
            models.UniqueConstraint(
                fields=("department", "store"), name="unique_department_per_store"
            )
        ]

    def __str__(self):
        return f"{self.department.name} · {self.store.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.department.slug}-at-{self.store.slug}"
            self.slug = build_unique_slug(StoreDepartment, base, self.pk)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = {*kwargs["update_fields"], "slug"}
        super().save(*args, **kwargs)


def build_unique_slug(model, base, pk=None, max_length=120):
    """Slugify `base`, adding -2, -3… until nothing else in `model` holds it."""
    base = slugify(base)[:max_length] or "item"
    candidate = base
    suffix = 2
    taken = model.objects.exclude(pk=pk) if pk else model.objects.all()
    while taken.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
