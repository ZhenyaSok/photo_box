import pytest

from apps.notifications.models import Notification, OutboxMessage


class TestNotificationService:
    """Тесты для NotificationService"""

    def test_create_notification_with_sms_default(self, db, notification_service):
        """Тест создания уведомления с методом по умолчанию (SMS)"""
        notification = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message"
        )

        assert notification.user_id == 1
        assert notification.title == "Test Title"
        assert notification.message == "Test Message"
        assert not notification.is_sent

        outbox_messages = notification.outbox_messages.all()
        assert outbox_messages.count() == 1
        assert outbox_messages[0].method == "SMS"
        assert outbox_messages[0].status == "PENDING"

    def test_create_notification_with_custom_methods(self, db, notification_service):
        """Тест создания уведомления с указанием методов"""
        notification = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message",
            methods=["EMAIL", "TELEGRAM"]
        )

        outbox_messages = notification.outbox_messages.all()
        assert outbox_messages.count() == 1
        assert outbox_messages[0].method == "EMAIL"

    def test_create_notification_without_methods(self, db, notification_service):
        """Тест создания уведомления без указания методов (должен использоваться SMS по умолчанию)"""
        notification = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message",
            methods=None
        )

        outbox_messages = notification.outbox_messages.all()
        assert outbox_messages.count() == 1
        assert outbox_messages[0].method == "SMS"

    def test_create_notification_with_empty_methods(self, db, notification_service):
        """Тест создания уведомления с пустым списком методов (должен использоваться SMS по умолчанию)"""
        notification = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message",
            methods=[]
        )

        outbox_messages = notification.outbox_messages.all()
        assert outbox_messages.count() == 1
        assert outbox_messages[0].method == "SMS"

    def test_create_notification_user_data_mapping(self, db, notification_service):
        """Тест что данные пользователя правильно маппятся для разных методов"""

        notification1 = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message",
            methods=["EMAIL"]
        )

        notification2 = notification_service.create_notification(
            user_id=2,
            title="Test Title",
            message="Test Message",
            methods=["SMS"]
        )

        outbox_message1 = notification1.outbox_messages.first()
        assert outbox_message1.payload["to_email"] == "test1@mail.ru"

        outbox_message2 = notification2.outbox_messages.first()
        assert outbox_message2.payload["phone"] == "+79007654321"

    def test_create_notification_unknown_user(self, db, notification_service):
        """Тест создания уведомления для неизвестного пользователя"""
        notification = notification_service.create_notification(
            user_id=999,
            title="Test Title",
            message="Test Message",
            methods=["EMAIL"]
        )

        outbox_messages = notification.outbox_messages.all()
        assert outbox_messages.count() == 1

        outbox_message = outbox_messages[0]
        assert outbox_message.payload["to_email"] is None

    def test_build_payload_email(self, notification_service, sample_notification):
        """Тест построения payload для email"""

        user_data = {"email": "test@example.com"}

        payload = notification_service._build_payload("EMAIL", sample_notification, user_data)

        assert payload["to_email"] == "test@example.com"
        assert payload["subject"] == "Test Notification"
        assert payload["message"] == "Test message"

    def test_build_payload_sms(self, notification_service, sample_notification):
        """Тест построения payload для sms"""
        user_data = {"phone": "+79001234567"}

        payload = notification_service._build_payload("SMS", sample_notification, user_data)

        assert payload["phone"] == "+79001234567"
        assert "Test Notification" in payload["message"]
        assert "Test message" in payload["message"]

    def test_build_payload_telegram(self, notification_service, sample_notification):
        """Тест построения payload для telegram"""
        user_data = {"telegram_chat_id": "123456789"}

        payload = notification_service._build_payload("TELEGRAM", sample_notification, user_data)

        assert payload["chat_id"] == "123456789"
        assert "*Test Notification*" in payload["message"]
        assert "Test message" in payload["message"]

    def test_build_payload_unknown_method(self, notification_service, sample_notification):
        """Тест построения payload для неизвестного метода"""
        user_data = {"email": "test@example.com"}

        payload = notification_service._build_payload("UNKNOWN", sample_notification, user_data)

        assert payload == {}

    @pytest.mark.parametrize("method,expected_keys", [
        ("EMAIL", ["to_email", "subject", "message"]),
        ("SMS", ["phone", "message"]),
        ("TELEGRAM", ["chat_id", "message"]),
        ("UNKNOWN", []),
    ])
    def test_build_payload_various_methods(self, notification_service, sample_notification, method, expected_keys):
        """Тест построения payload для разных методов"""
        user_data = {
            "email": "test@example.com",
            "phone": "+79001234567",
            "telegram_chat_id": "123456789"
        }

        payload = notification_service._build_payload(method, sample_notification, user_data)

        if expected_keys:
            assert all(key in payload for key in expected_keys)
        else:
            assert payload == {}

    def test_create_notification_transaction(self, db, notification_service):
        """Тест что создание уведомления происходит в транзакции"""

        notification = notification_service.create_notification(
            user_id=1,
            title="Test Title",
            message="Test Message"
        )

        assert Notification.objects.filter(id=notification.id).exists()
        assert OutboxMessage.objects.filter(notification=notification).exists()

    def test_create_notification_payload_structure(self, db, notification_service):
        """Тест структуры payload для разных методов"""
        test_cases = [
            ("EMAIL", {"to_email": "test1@mail.ru", "subject": "Test", "message": "Test Message"}),
            ("SMS", {"phone": "+79001234567", "message": "Test: Test Message"}),
            ("TELEGRAM", {"chat_id": "123456789", "message": "*Test*\nTest Message"}),
        ]

        for method, expected_payload in test_cases:
            notification = notification_service.create_notification(
                user_id=1,
                title="Test",
                message="Test Message",
                methods=[method]
            )

            outbox_message = notification.outbox_messages.first()
            assert outbox_message.method == method
            for key, value in expected_payload.items():
                assert outbox_message.payload[key] == value
