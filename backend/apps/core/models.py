import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base giving every row creation/update timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDTimeStampedModel(TimeStampedModel):
    """As above, with a UUID primary key — use for anything exposed publicly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
