from django.db import models

from .constants import NOTIFICATION_TYPES, DELIVERY_METHODS, NOTIFICATION_STATUS
from ..core.models import BaseModel


class Notification(BaseModel):
    """Модель уведомления"""
    user_id = models.IntegerField()
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='INFO'
    )
    is_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (user: {self.user_id})"


class OutboxMessage(BaseModel):
    """
    Модель для хранения исходящих сообщений в outbox паттерне.
    Обеспечивает надежную доставку через механизм повторных попыток."""
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.method} - {self.status} (attempts: {self.attempt_count})"
