from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.notifications.models import Notification
from apps.notifications.serializers import CreateNotificationSerializer, NotificationSerializer
from apps.notifications.services import NotificationService


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return CreateNotificationSerializer
        return NotificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        service = NotificationService()

        notification = service.create_notification(
            user_id=data["user_id"],
            title=data["title"],
            message=data["message"],
            methods=data.get("delivery_methods", ["SMS"]),
        )

        return Response(
            {"id": notification.id, "status": "created"}, status=status.HTTP_201_CREATED
        )
