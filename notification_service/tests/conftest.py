import os
from unittest.mock import Mock

import django
import pytest
from rest_framework.test import APIClient

from apps.notifications.models import Notification, OutboxMessage
from apps.notifications.services import NotificationService

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "photo_box.settings")
django.setup()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def notification_service():
    return NotificationService()


@pytest.fixture
@pytest.mark.django_db
def sample_notification(db):
    return Notification.objects.create(
        user_id=1, title="Test Notification", message="Test message"
    )


@pytest.fixture
@pytest.mark.django_db
def sample_outbox_message(db, sample_notification):
    return OutboxMessage.objects.create(
        notification=sample_notification,
        method="SMS",
        payload={"phone": "+79001234567", "message": "Test message"},
    )


@pytest.fixture
def mock_delivery_service():
    mock = Mock()
    mock.send_via_method.return_value = True
    return mock
