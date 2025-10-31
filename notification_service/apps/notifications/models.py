import uuid

from django.db import models

from .constants import NOTIFICATION_TYPES, DELIVERY_METHODS, NOTIFICATION_STATUS


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.IntegerField()
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='INFO'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']


class OutboxMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='outbox_messages'
    )
    method = models.CharField(max_length=20, choices=DELIVERY_METHODS)
    status = models.CharField(
        max_length=20,
        choices=NOTIFICATION_STATUS,
        default='PENDING'
    )
    payload = models.JSONField()
    attempt_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    last_attempt = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['notification', 'method']),
        ]
