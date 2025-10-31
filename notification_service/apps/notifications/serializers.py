from rest_framework import serializers
from .models import Notification, OutboxMessage, NotificationMethod

class CreateNotificationSerializer(serializers.ModelSerializer):
    delivery_methods = serializers.ListField(
        child=serializers.ChoiceField(choices=NotificationMethod.choices),
        default=[NotificationMethod.SMS],
        required=False
    )

    class Meta:
        model = Notification
        fields = ['user_id', 'title', 'message', 'delivery_methods']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user_id', 'title', 'message', 'is_sent', 'created_at']
        read_only_fields = ['id', 'is_sent', 'created_at']

class OutboxMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxMessage
        fields = ['id', 'method', 'status', 'attempt_count', 'last_attempt', 'created_at']
        read_only_fields = fields