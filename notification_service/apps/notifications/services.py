from typing import List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.notifications.gateways import DeliveryService
from apps.notifications.models import Notification, NotificationMethod, OutboxMessage, OutboxStatus


class NotificationService:
    @transaction.atomic
    def create_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        methods: Optional[List[str]] = None,
    ):
        if not methods:
            methods = [NotificationMethod.SMS]

        notification = Notification.objects.create(
            user_id=user_id, title=title, message=message
        )

        user_data = self._get_user_data(user_id)

        for method in methods:
            OutboxMessage.objects.create(
                notification=notification,
                method=method,
                payload=self._build_payload(method, notification, user_data),
            )

        return notification

    def get_pending_messages(self, limit=50):
        """Получение ожидающих сообщений"""
        return OutboxMessage.objects.select_for_update(skip_locked=True).filter(
            Q(status=OutboxStatus.PENDING)
            | Q(
                status=OutboxStatus.ENQUEUED,
                status_changed_at__lte=timezone.now() - timezone.timedelta(minutes=1),
            )
        )[:limit]

    def process_single_outbox_message(self, outbox_message_id):
        """Обработка одного сообщения"""
        try:
            with transaction.atomic():
                message = (
                    OutboxMessage.objects.select_for_update(skip_locked=True)
                    .filter(id=outbox_message_id, status=OutboxStatus.ENQUEUED)
                    .first()
                )

                if not message:
                    return {"status": "skipped", "reason": "not_found"}

                # Проверяем, не отправлено ли уже уведомление
                if message.notification.is_sent:
                    # Если уведомление уже отправлено, помечаем все связанные сообщения как отправленные
                    OutboxMessage.objects.filter(
                        notification=message.notification, status=OutboxStatus.ENQUEUED
                    ).update(status=OutboxStatus.SENT)
                    return {"status": "sent", "reason": "already_sent"}

                if not message.can_retry():
                    message.mark_failed("Превышен лимит повторных попыток")
                    message.create_fallback()
                    return {"status": "failed", "reason": "retry_limit"}

                message.start_processing()

            success = DeliveryService().send_via_method(
                message.method, message.notification, message.payload
            )

            with transaction.atomic():
                message = OutboxMessage.objects.select_for_update().get(
                    id=outbox_message_id
                )
                if success:
                    message.mark_success()
                    # Помечаем все уведомление как отправленное
                    message.notification.is_sent = True
                    message.notification.save()
                    return {"status": "sent", "method": message.method}
                else:
                    message.mark_failed(f"Не удалось отправить через {message.method}")
                    raise Exception(f"Failed to send via {message.method}")

        except Exception as e:
            # Если это не ошибка отправки, пробрасываем дальше
            if "Failed to send via" in str(e):
                raise e
            return {"status": "error", "reason": str(e)}

    def _get_user_data(self, user_id: int):
        """Получение данных пользователя"""
        user_data = {
            1: {
                "email": "test1@mail.ru",
                "phone": "+79001234567",
                "telegram_chat_id": "123456789",
            },
            2: {
                "email": "test2@mail.ru",
                "phone": "+79007654321",
                "telegram_chat_id": "987654321",
            },
        }
        return user_data.get(user_id, {})

    def _build_payload(self, method: str, notification: Notification, user_data: dict):
        if method == NotificationMethod.EMAIL:
            return {
                "to_email": user_data.get("email"),
                "subject": notification.title,
                "message": notification.message,
            }
        elif method == NotificationMethod.SMS:
            return {
                "phone": user_data.get("phone"),
                "message": f"{notification.title}: {notification.message}",
            }
        elif method == NotificationMethod.TELEGRAM:
            return {
                "chat_id": user_data.get("telegram_chat_id"),
                "message": f"*{notification.title}*\n{notification.message}",
            }
        return {}
