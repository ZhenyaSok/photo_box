from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Notification
from .serializers import CreateNotificationSerializer
from .services import NotificationService
from .tasks import process_notification_fallback


class NotificationViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = CreateNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        service = NotificationService()

        notification = service.create_with_fallback(
            user_id=data['user_id'],
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', 'INFO'),
            methods=data.get('delivery_methods', ['EMAIL', 'SMS', 'TELEGRAM'])
        )

        process_notification_fallback.delay(notification.id)

        return Response(
            {'id': notification.id, 'status': 'processing'},
            status=status.HTTP_201_CREATED
        )