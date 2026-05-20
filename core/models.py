import uuid
from django.db import models

class SyncBaseModel(models.Model):
    """Base model for all objects that need to be synced offline"""
    # We use uuid as the primary key for all models to support offline creation without collisions
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class TenantManager(models.Manager):
    """Manager for single-tenancy (just returns all objects)"""
    def get_queryset(self):
        return super().get_queryset()
