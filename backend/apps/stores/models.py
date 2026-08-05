from django.db import models

from apps.core.models import TimeStampedModel


class Store(TimeStampedModel):
    """A Moriarty Group branch. Seeded with the three live stores."""

    code = models.CharField(max_length=16, unique=True, help_text="SuperValu store number.")
    slug = models.SlugField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name
