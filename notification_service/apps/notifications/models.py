from typing import Optional

from django.db import models
from django.utils import timezone


class OutboxStatus(models.TextChoices):
    PENDING = 'PENDING', 'В ожидании'
    ENQUEUED = 'ENQUEUED', 'В очереди'
    SENT = 'SENT', 'Отправлено'
    FAILED = 'FAILED', 'Не удалось'


class NotificationMethod(models.TextChoices):
    SMS = 'SMS', 'SMS'
    EMAIL = 'EMAIL', 'Email'
    TELEGRAM = 'TELEGRAM', 'Telegram'


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Notification(BaseModel):
    user_id = models.IntegerField()
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} (user: {self.user_id})"


class OutboxMessage(BaseModel):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='outbox_messages')
    method = models.CharField(max_length=20, choices=NotificationMethod.choices)
    status = models.CharField(max_length=20, choices=OutboxStatus.choices, default=OutboxStatus.PENDING)
    payload = models.JSONField()
    attempt_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    last_attempt = models.DateTimeField(null=True, blank=True)
    status_changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.method} - {self.status} (attempts: {self.attempt_count})"

    def can_retry(self):
        return self.attempt_count < self.max_retries

    def start_processing(self):
        self.attempt_count += 1
        self.last_attempt = timezone.now()
        self.save()

    def mark_success(self):
        self.status = OutboxStatus.SENT
        self.status_changed_at = timezone.now()
        self.save()

    def mark_failed(self, reason=""):
        self.status = OutboxStatus.FAILED
        self.status_changed_at = timezone.now()
        self.save()

    def get_next_fallback_method(self) -> Optional[str]:
        methods = ['SMS', 'TELEGRAM', 'EMAIL']
        try:
            current_index = methods.index(self.method)
            if current_index + 1 < len(methods):
                return methods[current_index + 1]
        except ValueError:
            pass
        return None

    def create_fallback(self):
        next_method = self.get_next_fallback_method()
        if next_method and not self.notification.is_sent:
            return OutboxMessage.objects.create(
                notification=self.notification,
                method=next_method,
                status=OutboxStatus.PENDING,
                payload=self.payload
            )
        return None
