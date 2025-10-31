from typing import List, Optional

from django.db import transaction

from .models import Notification, OutboxMessage, NotificationMethod


class NotificationService:
    @transaction.atomic
    def create_notification(self, user_id: int, title: str, message: str, methods: Optional[List[str]] = None):
        if not methods:
            methods = [NotificationMethod.SMS]

        notification = Notification.objects.create(
            user_id=user_id,
            title=title,
            message=message
        )

        user_data = {
            1: {"email": "test1@mail.ru", "phone": "+79001234567", "telegram_chat_id": "123456789"},
            2: {"email": "test2@mail.ru", "phone": "+79007654321", "telegram_chat_id": "987654321"},
        }.get(user_id, {})

        OutboxMessage.objects.create(
            notification=notification,
            method=methods[0],
            payload=self._build_payload(methods[0], notification, user_data)
        )

        return notification

    def _build_payload(self, method: str, notification: Notification, user_data: dict):
        if method == NotificationMethod.EMAIL:
            return {"to_email": user_data.get("email"), "subject": notification.title, "message": notification.message}
        elif method == NotificationMethod.SMS:
            return {"phone": user_data.get("phone"), "message": f"{notification.title}: {notification.message}"}
        elif method == NotificationMethod.TELEGRAM:
            return {"chat_id": user_data.get("telegram_chat_id"),
                    "message": f"*{notification.title}*\n{notification.message}"}
        return {}
