from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status


class TestNotificationViewSet:
    """Тесты для API endpoints"""

    @patch("apps.notifications.views.NotificationService")
    def test_create_notification_success(self, mock_service, api_client):
        """Тест успешного создания уведомления"""
        mock_instance = MagicMock()
        mock_service.return_value = mock_instance

        mock_notification = MagicMock()
        mock_notification.id = 1
        mock_instance.create_notification.return_value = mock_notification

        data = {
            "user_id": 1,
            "title": "Test Notification",
            "message": "Test message",
            "delivery_methods": ["SMS", "EMAIL"],
        }

        # Возвращаем прежний URL
        response = api_client.post("/api/notifications/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] == 1
        assert response.data["status"] == "created"

        mock_instance.create_notification.assert_called_once_with(
            user_id=1,
            title="Test Notification",
            message="Test message",
            methods=["SMS", "EMAIL"],
        )

    def test_create_notification_invalid_data(self, api_client):
        """Тест создания уведомления с невалидными данными"""
        data = {
            "user_id": "invalid",  # Должен быть integer
            "title": "",  # Не может быть пустым
            "message": "Test message",
        }

        response = api_client.post("/api/notifications/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_list_notifications(self, api_client):
        """Тест получения списка уведомлений"""
        from apps.notifications.models import Notification

        Notification.objects.create(
            user_id=1, title="Test Notification", message="Test message"
        )

        response = api_client.get("/api/notifications/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    @pytest.mark.django_db
    def test_retrieve_notification(self, api_client):
        """Тест получения конкретного уведомления"""
        from apps.notifications.models import Notification

        notification = Notification.objects.create(
            user_id=1, title="Test Notification", message="Test message"
        )

        response = api_client.get(f"/api/notifications/{notification.id}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == notification.id

    @pytest.mark.django_db
    def test_retrieve_notification_not_found(self, api_client):
        """Тест получения несуществующего уведомления"""
        response = api_client.get("/api/notifications/999/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
