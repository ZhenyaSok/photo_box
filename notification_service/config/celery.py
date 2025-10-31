import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('notification_service')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'process-pending-outbox-every-10s': {
        'task': 'apps.notifications.tasks.process_pending_outbox_messages',
        'schedule': 10.0,
    },
}

app.conf.timezone = 'UTC'