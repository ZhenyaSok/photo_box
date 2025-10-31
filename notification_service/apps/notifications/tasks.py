from celery import shared_task

from .models import Notification
from .services import NotificationService


@shared_task
def process_notification_fallback(notification_id):
    try:
        notification = Notification.objects.get(id=notification_id)
        service = NotificationService()
        success = service.process_fallback_delivery(notification)

        return {"notification_id": str(notification_id), "success": success}
    except Notification.DoesNotExist:
        return {"error": "Notification not found"}
    except Exception as e:
        return {"error": str(e)}
