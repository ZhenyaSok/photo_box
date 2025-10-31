from django.db import models
from .constants import NOTIFICATION_TYPES, DELIVERY_METHODS, NOTIFICATION_STATUS


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Notification(BaseModel):
    user_id = models.IntegerField()
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='INFO'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} (user: {self.user_id})"


class OutboxMessage(BaseModel):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    method = models.CharField(max_length=20, choices=DELIVERY_METHODS)
    status = models.CharField(
        max_length=20,
        choices=NOTIFICATION_STATUS,
        default='PENDING'
    )
    attempt_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']