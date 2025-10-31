from celery import shared_task
from django.utils import timezone
from django.db import transaction, models
import logging
from .models import Notification

from .gateways import DeliveryService
from .models import OutboxMessage
from .services import OutboxService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_outbox_message(self, outbox_message_id):
    """Обработка одного outbox сообщения"""
    try:
        with transaction.atomic():
            outbox_message = OutboxMessage.objects.select_for_update().get(
                id=outbox_message_id
            )

            if outbox_message.attempt_count >= outbox_message.max_retries:
                logger.warning(f"Сообщение {outbox_message_id} превысило лимит повторов")
                return {
                    'status': 'failed',
                    'reason': 'retry_limit_exceeded',
                    'message_id': str(outbox_message_id)
                }

            outbox_message.status = 'PROCESSING'
            outbox_message.attempt_count += 1
            outbox_message.last_attempt = timezone.now()
            outbox_message.save()

        delivery_service = DeliveryService()
        success = delivery_service.send_via_method(
            outbox_message.method,
            outbox_message.notification,
            outbox_message.payload
        )

        with transaction.atomic():
            outbox_message = OutboxMessage.objects.get(id=outbox_message_id)

            if success:
                outbox_message.status = 'SENT'
                outbox_message.error_message = ''

                # Помечаем уведомление как отправленное
                notification = outbox_message.notification
                if not notification.is_sent:
                    notification.is_sent = True
                    notification.save()

                logger.info(f"Сообщение {outbox_message_id} доставлено через {outbox_message.method}")
            else:
                outbox_message.status = 'FAILED'
                outbox_message.error_message = f"Не удалось доставить через {outbox_message.method}"

                if outbox_message.attempt_count < outbox_message.max_retries:
                    retry_delay = 60 * outbox_message.attempt_count  # Экспоненциальная задержка
                    logger.info(f"Сообщение {outbox_message_id} не доставлено, повторная попытка через {retry_delay}с")
                    self.retry(countdown=retry_delay)
                else:
                    logger.error(f"Сообщение {outbox_message_id} не доставлено после {outbox_message.attempt_count} попыток")

            outbox_message.save()

        return {
            'message_id': str(outbox_message_id),
            'status': 'sent' if success else 'failed',
            'method': outbox_message.method,
            'attempt': outbox_message.attempt_count,
            'notification_id': str(outbox_message.notification.id)
        }

    except OutboxMessage.DoesNotExist:
        logger.error(f"OutboxMessage {outbox_message_id} не найден")
        return {
            'status': 'error',
            'reason': 'not_found',
            'message_id': str(outbox_message_id)
        }
    except Exception as exc:
        logger.error(f"Ошибка обработки outbox сообщения {outbox_message_id}: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task
def process_pending_outbox_messages():
    """Периодическая задача для обработки ожидающих сообщений"""
    try:
        outbox_service = OutboxService()
        pending_messages = outbox_service.get_pending_messages(limit=50)

        processed_count = 0
        for message in pending_messages:
            process_outbox_message.delay(str(message.id))
            processed_count += 1

        logger.info(f"Запланировано {processed_count} outbox сообщений для обработки")
        return {
            'task': 'process_pending_outbox_messages',
            'processed_count': processed_count,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка в process_pending_outbox_messages: {str(e)}")
        return {
            'task': 'process_pending_outbox_messages',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def retry_failed_outbox_messages():
    """Повторная обработка сообщений с статусом FAILED"""
    try:

        failed_messages = OutboxMessage.objects.filter(
            status='FAILED',
            attempt_count__lt=models.F('max_retries'),
            last_attempt__lt=timezone.now() - timezone.timedelta(minutes=5)
        )

        retry_count = 0
        for message in failed_messages:
            message.status = 'PENDING'
            message.save()

            process_outbox_message.delay(str(message.id))
            retry_count += 1

        logger.info(f"Повторно отправлено {retry_count} неудачных сообщений")
        return {
            'task': 'retry_failed_outbox_messages',
            'retry_count': retry_count,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка в retry_failed_outbox_messages: {str(e)}")
        return {
            'task': 'retry_failed_outbox_messages',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def cleanup_old_outbox_messages(days_old=30):
    """Очистка старых отправленных сообщений"""
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)

        deleted_count = OutboxMessage.objects.filter(
            status='SENT',
            created_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Очищено {deleted_count} старых outbox сообщений")
        return {
            'task': 'cleanup_old_outbox_messages',
            'deleted_count': deleted_count,
            'days_old': days_old,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка в cleanup_old_outbox_messages: {str(e)}")
        return {
            'task': 'cleanup_old_outbox_messages',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def send_immediate_notification(user_id, title, message, notification_type='INFO', delivery_methods=None):
    """Немедленная отправка уведомления (обертка для удобства)"""
    try:
        from .services import OutboxService

        if delivery_methods is None:
            delivery_methods = ['EMAIL', 'SMS', 'TELEGRAM']

        outbox_service = OutboxService()

        notification, outbox_messages = outbox_service.create_notification_with_outbox(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            delivery_methods=delivery_methods
        )

        for outbox_message in outbox_messages:
            process_outbox_message.delay(str(outbox_message.id))

        return {
            'task': 'send_immediate_notification',
            'notification_id': str(notification.id),
            'outbox_messages_count': len(outbox_messages),
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка в send_immediate_notification: {str(e)}")
        return {
            'task': 'send_immediate_notification',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }


@shared_task
def monitor_system_health():
    """Мониторинг здоровья системы уведомлений"""
    try:

        total_notifications = Notification.objects.count()
        sent_notifications = Notification.objects.filter(is_sent=True).count()
        failed_notifications = Notification.objects.filter(is_sent=False).count()

        outbox_stats = OutboxMessage.objects.aggregate(
            total=models.Count('id'),
            pending=models.Count('id', filter=models.Q(status='PENDING')),
            processing=models.Count('id', filter=models.Q(status='PROCESSING')),
            sent=models.Count('id', filter=models.Q(status='SENT')),
            failed=models.Count('id', filter=models.Q(status='FAILED')),
        )

        health_status = {
            'task': 'monitor_system_health',
            'timestamp': timezone.now().isoformat(),
            'notifications': {
                'total': total_notifications,
                'sent': sent_notifications,
                'failed': failed_notifications,
                'success_rate': (sent_notifications / total_notifications * 100) if total_notifications > 0 else 0
            },
            'outbox': outbox_stats,
            'system': {
                'status': 'healthy' if sent_notifications > failed_notifications else 'degraded',
                'message': 'Система работает нормально' if sent_notifications > failed_notifications else 'Обнаружен высокий процент ошибок'
            }
        }

        logger.info(f"Проверка состояния системы: {health_status}")
        return health_status

    except Exception as e:
        logger.error(f"Ошибка в monitor_system_health: {str(e)}")
        return {
            'task': 'monitor_system_health',
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
            'system': {'status': 'error'}
        }


@shared_task
def force_process_telegram_messages():
    """Принудительная обработка всех Telegram сообщений"""
    try:
        telegram_messages = OutboxMessage.objects.filter(
            method='TELEGRAM',
            status__in=['PENDING', 'FAILED']
        )

        processed_count = 0
        for message in telegram_messages:

            process_outbox_message.delay(str(message.id))
            processed_count += 1

        return {
            'task': 'force_process_telegram_messages',
            'processed_count': processed_count,
            'timestamp': timezone.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка в force_process_telegram_messages: {str(e)}")
        return {
            'task': 'force_process_telegram_messages',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }