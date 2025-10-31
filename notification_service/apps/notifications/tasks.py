import logging

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .gateways import DeliveryService
from .models import OutboxMessage, OutboxStatus

logger = logging.getLogger(__name__)


@shared_task
def process_pending_outbox_messages():
    """Берет 50 сообщений и ставит их в очередь"""
    with transaction.atomic():

        pending_messages = OutboxMessage.objects.select_for_update(skip_locked=True).filter(
            Q(status=OutboxStatus.PENDING) |
            Q(status=OutboxStatus.ENQUEUED, status_changed_at__lte=timezone.now() - timezone.timedelta(minutes=1))
        )[:50]

        for message in pending_messages:
            message.status = OutboxStatus.ENQUEUED
            message.status_changed_at = timezone.now()
            message.save()

        for message in pending_messages:
            process_single_outbox_message.delay(message.id)

        logger.info(f"Поставлено в очередь {len(pending_messages)} сообщений для обработки")
        return {"enqueued": len(pending_messages)}


@shared_task(bind=True, max_retries=3)
def process_single_outbox_message(self, outbox_message_id):
    """Обработка одного сообщения с 3 попытками"""
    with transaction.atomic():
        message = OutboxMessage.objects.select_for_update(skip_locked=True).filter(
            id=outbox_message_id,
            status=OutboxStatus.ENQUEUED
        ).first()

        if not message:
            return {"status": "skipped", "reason": "not_found"}

        if not message.can_retry():
            logger.warning(f"Сообщение {outbox_message_id} превысило лимит повторов")
            message.mark_failed("Превышен лимит повторных попыток")
            message.create_fallback()
            return {"status": "failed", "reason": "retry_limit"}

        message.start_processing()

    try:
        success = DeliveryService().send_via_method(
            message.method,
            message.notification,
            message.payload
        )
    except Exception as e:
        success = False
        logger.error(f"Ошибка отправки сообщения {outbox_message_id}: {str(e)}")

    with transaction.atomic():
        message = OutboxMessage.objects.select_for_update().get(id=outbox_message_id)

        if success:
            message.mark_success()
            message.notification.is_sent = True
            message.notification.save()
            logger.info(f"Сообщение {outbox_message_id} отправлено через {message.method}")
            return {"status": "sent", "method": message.method}
        else:
            message.mark_failed(f"Не удалось отправить через {message.method}")

            if message.can_retry():
                retry_delay = 10 * (2 ** message.attempt_count)
                logger.info(f"Повторная отправка сообщения {outbox_message_id} через {retry_delay}с")
                raise self.retry(countdown=retry_delay)
            else:

                fallback = message.create_fallback()
                if fallback:
                    logger.info(f"Создано резервное сообщение {fallback.id} с методом {fallback.method}")
                return {"status": "failed", "method": message.method}
