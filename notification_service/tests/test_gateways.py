from unittest.mock import MagicMock, patch

import pytest

from apps.notifications.gateways import (
    DeliveryService,
    EmailGateway,
    SMSGateway,
    TelegramGateway,
)
from apps.notifications.models import Notification


class TestEmailGateway:
    """Тесты для EmailGateway"""

    @pytest.fixture
    def email_gateway(self):
        return EmailGateway()

    @pytest.fixture
    def sample_notification(self, db):
        return Notification.objects.create(
            user_id=1, title="Test Title", message="Test Message"
        )

    @patch("apps.notifications.gateways.send_mail")
    def test_send_email_success(
        self, mock_send_mail, email_gateway, sample_notification
    ):
        """Тест успешной отправки email"""
        mock_send_mail.return_value = None

        payload = {
            "to_email": "test@example.com",
            "subject": "Test Subject",
            "message": "Test Message",
        }

        result = email_gateway.send(sample_notification, payload)

        assert result is True
        mock_send_mail.assert_called_once()

    @patch("apps.notifications.gateways.send_mail")
    def test_send_email_default_values(
        self, mock_send_mail, email_gateway, sample_notification
    ):
        """Тест отправки email с значениями по умолчанию"""
        mock_send_mail.return_value = None

        payload = {}

        result = email_gateway.send(sample_notification, payload)

        assert result is True
        call_kwargs = mock_send_mail.call_args[1]
        assert call_kwargs["subject"] == "Test Title"
        assert call_kwargs["message"] == "Test Message"


class TestSMSGateway:
    """Тесты для SMSGateway"""

    @pytest.fixture
    def sms_gateway(self):
        return SMSGateway()

    def test_send_sms_no_phone(self, sms_gateway, sample_notification):
        """Тест отправки SMS без номера телефона"""
        payload = {"phone": None, "message": "Test SMS Message"}

        result = sms_gateway.send(sample_notification, payload)

        assert result is False


class TestTelegramGateway:
    """Тесты для TelegramGateway"""

    @pytest.fixture
    def telegram_gateway(self):
        return TelegramGateway()

    @patch("apps.notifications.gateways.os.getenv")
    @patch("apps.notifications.gateways.requests.post")
    def test_send_telegram_success(
        self, mock_post, mock_getenv, telegram_gateway, sample_notification
    ):
        """Тест успешной отправки в Telegram"""
        mock_getenv.return_value = "123456789"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        payload = {"chat_id": "123456789", "message": "Test Telegram Message"}

        result = telegram_gateway.send(sample_notification, payload)

        assert result is True
        mock_post.assert_called_once()

    @patch("apps.notifications.gateways.os.getenv")
    def test_send_telegram_no_chat_id(
        self, mock_getenv, telegram_gateway, sample_notification
    ):
        """Тест отправки в Telegram без chat_id"""
        mock_getenv.return_value = None

        payload = {"chat_id": "123456789", "message": "Test Telegram Message"}

        result = telegram_gateway.send(sample_notification, payload)

        assert result is False


class TestDeliveryService:
    """Тесты для DeliveryService"""

    @pytest.fixture
    def delivery_service(self):
        return DeliveryService()

    @pytest.mark.parametrize(
        "method,expected_gateway",
        [
            ("EMAIL", "EmailGateway"),
            ("SMS", "SMSGateway"),
            ("TELEGRAM", "TelegramGateway"),
        ],
    )
    def test_send_via_method_various_gateways(
        self, delivery_service, sample_notification, method, expected_gateway
    ):
        """Тест отправки через разные шлюзы"""
        with patch(f"apps.notifications.gateways.{expected_gateway}.send") as mock_send:
            mock_send.return_value = True

            payload = {"test": "data"}
            result = delivery_service.send_via_method(
                method, sample_notification, payload
            )

            assert result is True
            mock_send.assert_called_once_with(sample_notification, payload)

    def test_send_via_method_unknown(self, delivery_service, sample_notification):
        """Тест отправки через неизвестный метод"""
        payload = {"test": "data"}
        result = delivery_service.send_via_method(
            "UNKNOWN", sample_notification, payload
        )

        assert result is False
