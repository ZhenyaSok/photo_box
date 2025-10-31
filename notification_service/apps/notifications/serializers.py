from rest_framework import serializers
from .models import Notification
from .constants import DELIVERY_METHODS

class CreateNotificationSerializer(serializers.ModelSerializer):
    delivery_methods = serializers.ListField(
        child=serializers.ChoiceField(choices=DELIVERY_METHODS),
        default=['EMAIL', 'SMS', 'TELEGRAM']
    )

    class Meta:
        model = Notification
        fields = ['user_id', 'title', 'message', 'notification_type', 'delivery_methods']