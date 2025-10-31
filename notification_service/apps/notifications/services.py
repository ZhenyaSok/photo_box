import os
import time

from django.db import transaction
from .models import Notification, OutboxMessage
from .gateways import DeliveryService


class NotificationService:

    @transaction.atomic
    def create_with_fallback(self, user_id, title, message, notification_type='INFO', methods=None):
        if methods is None:
            methods = ['EMAIL', 'SMS', 'TELEGRAM']

        notification = Notification.objects.create(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type
        )

        for method in methods:
            OutboxMessage.objects.create(
                notification=notification,
                method=method,
                status='PENDING'
            )

        return notification

    def process_fallback_delivery(self, notification):
        outbox_messages = notification.outboxmessage_set.all()

        for outbox_msg in outbox_messages:
            if outbox_msg.status == 'SENT':
                continue

            success = self._try_send(outbox_msg, max_retries=3)

            if success:
                notification.outboxmessage_set.update(status='SENT')
                return True

        return False

    def _try_send(self, outbox_msg, max_retries=3):
        """Упрощенная версия с повторными попытками без try/except"""
        user_data = self._get_user_data(outbox_msg.notification.user_id)
        payload = self._build_payload(outbox_msg.method, outbox_msg.notification, user_data)

        for attempt in range(max_retries):
            success = DeliveryService().send_via_method(
                outbox_msg.method,
                outbox_msg.notification,
                payload
            )

            if success:
                # УСПЕХ - сохраняем и возвращаем
                outbox_msg.attempt_count = attempt + 1
                outbox_msg.status = 'SENT'
                outbox_msg.save()
                return True
            else:

                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)

        outbox_msg.attempt_count = max_retries
        outbox_msg.status = 'FAILED'
        outbox_msg.save()
        return False

    def _get_user_data(self, user_id):
        test_users = {
            1: {'email': os.getenv("EMAIL_HOST_USER"), 'phone': '+79001234567', 'telegram_chat_id': os.getenv("CHAT_ID")},
            2: {'email': 'test2@mail.ru', 'phone': '+79007654321', 'telegram_chat_id': '987654321'},
        }
        return test_users.get(user_id, {})

    def _build_payload(self, method, notification, user_data):
        if method == 'EMAIL':
            return {
                'to_email': user_data.get('email', os.getenv("EMAIL_HOST_USER")),
                'subject': notification.title,
                'message': notification.message
            }
        elif method == 'SMS':
            return {
                'phone': user_data.get('phone', '+79000000000'),
                'message': f"{notification.title}: {notification.message}"
            }
        elif method == 'TELEGRAM':
            return {
                'chat_id': user_data.get('telegram_chat_id', os.getenv("CHAT_ID")),
                'message': f"*{notification.title}*\n{notification.message}"
            }
        return {}