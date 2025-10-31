import logging

from django.db import models, transaction

from .gateways import DeliveryService
from .models import Notification, OutboxMessage

logger = logging.getLogger(__name__)


class OutboxService:
    """Сервис для работы с Outbox сообщениями"""

    def __init__(self):
        self.delivery_service = DeliveryService()

    @transaction.atomic
    def create_notification_with_outbox(self, user_id, title, message, notification_type='INFO', delivery_methods=None):
        """Создание уведомления и outbox сообщений в одной транзакции"""
        if delivery_methods is None:
            delivery_methods = ['EMAIL', 'SMS', 'TELEGRAM']

        notification = Notification.objects.create(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type
        )

        # Получаем данные пользователя (заглушка)
        user_data = self._get_user_data(user_id)

        outbox_messages = []
        for method in delivery_methods:
            outbox_message = OutboxMessage.objects.create(
                notification=notification,
                method=method,
                payload=self._build_payload(method, notification, user_data)
            )
            outbox_messages.append(outbox_message)

        return notification, outbox_messages

    def _get_user_data(self, user_id):
        """Получение данных пользователя - ТЕСТОВЫЕ ДАННЫЕ"""
        test_users = {
            1: {
                'email': 'kapitan_kub@mail.ru',
                'phone': '+79085898807',
                'telegram_chat_id': '7722429828'
            },
            2: {
                'email': 'user2@example.com',
                'phone': '+79160000001',
            },
        }

        return test_users.get(user_id, {
            'email': f'user{user_id}@example.com',
            'phone': '+79160000000',
            'telegram_chat_id': None
        })

    def _build_payload(self, method, notification, user_data):
        """Построение payload для разных методов доставки"""

        if method == 'EMAIL':
            payload = {
                'to_email': user_data['email'],
                'subject': notification.title,
                'message': notification.message
            }

            return payload

        elif method == 'SMS':
            payload = {
                'phone': user_data['phone'],
                'message': f"{notification.title}: {notification.message}"
            }

            return payload

        elif method == 'TELEGRAM':
            payload = {
                'chat_id': user_data['telegram_chat_id'],
                'message': f"*{notification.title}*\n{notification.message}"
            }

            return payload

        return {}

    def get_pending_messages(self, limit=100):
        """Получить ожидающие обработки сообщения"""
        return OutboxMessage.objects.filter(
            status__in=['PENDING', 'FAILED'],
            attempt_count__lt=models.F('max_retries')
        ).select_related('notification')[:limit]
