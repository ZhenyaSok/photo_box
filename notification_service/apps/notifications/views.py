from rest_framework import viewsets, status
from rest_framework.response import Response

from .models import Notification
from .serializers import CreateNotificationSerializer, NotificationSerializer
from .services import NotificationService


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateNotificationSerializer
        return NotificationSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        service = NotificationService()

        notification = service.create_notification(
            user_id=data['user_id'],
            title=data['title'],
            message=data['message'],
            methods=data.get('delivery_methods', ['SMS'])
        )

        return Response(
            {'id': notification.id, 'status': 'created'},
            status=status.HTTP_201_CREATED
        )
