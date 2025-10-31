from rest_framework import serializers
from .models import Notification, OutboxMessage
from .constants import DELIVERY_METHODS


class OutboxMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboxMessage
        fields = [
            'id', 'method', 'status', 'attempt_count',
            'last_attempt', 'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    outbox_messages = OutboxMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user_id', 'title', 'message', 'notification_type',
            'created_at', 'updated_at', 'is_sent', 'outbox_messages'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreateNotificationSerializer(serializers.ModelSerializer):
    delivery_methods = serializers.ListField(
        child=serializers.ChoiceField(choices=DELIVERY_METHODS),
        default=['EMAIL', 'SMS', 'TELEGRAM']
    )

    class Meta:
        model = Notification
        fields = [
            'user_id', 'title', 'message',
            'notification_type', 'delivery_methods'
        ]