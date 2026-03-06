import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class InviteManager(models.Manager):
    def create_invite(self, created_by):
        return self.create(
            created_by=created_by,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def get_by_token(self, token):
        try:
            return self.get(token=token)
        except self.model.DoesNotExist:
            return None

    def get_all_invites(self):
        return self.all().order_by('-created_at')


class Invite(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='invites_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invite_used',
    )
    used_at = models.DateTimeField(null=True, blank=True)

    objects = InviteManager()

    @property
    def is_valid(self):
        return self.used_by is None and timezone.now() < self.expires_at

    def __str__(self):
        return str(self.token)
