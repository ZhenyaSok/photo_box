from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Notification, OutboxMessage
from .serializers import NotificationSerializer, CreateNotificationSerializer, OutboxMessageSerializer
from .services import OutboxService
from .tasks import process_pending_outbox_messages
from django.db import connection
from django.core.cache import cache


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user_id', 'notification_type', 'is_sent']

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateNotificationSerializer
        return NotificationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        outbox_service = OutboxService()

        notification, outbox_messages = outbox_service.create_notification_with_outbox(
            user_id=data['user_id'],
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', 'INFO'),
            delivery_methods=data.get('delivery_methods', ['EMAIL', 'SMS', 'TELEGRAM'])
        )

        process_pending_outbox_messages.delay()

        response_serializer = NotificationSerializer(notification)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def retry_delivery(self, request, pk=None):

        notification = self.get_object()

        outbox_messages = notification.outbox_messages.filter(status='FAILED')
        for message in outbox_messages:
            message.status = 'PENDING'
            message.attempt_count = 0
            message.error_message = ''
            message.save()

        process_pending_outbox_messages.delay()

        return Response({
            'status': 'retry_initiated',
            'messages_retried': outbox_messages.count()
        })

    @action(detail=False, methods=['post'])
    def process_pending(self, request):
        """Ручной запуск обработки ожидающих сообщений"""
        result = process_pending_outbox_messages.delay()
        return Response({
            'status': 'processing_started',
            'task_id': result.id
        })


class OutboxMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для просмотра outbox сообщений"""
    queryset = OutboxMessage.objects.all()
    serializer_class = OutboxMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification', 'method', 'status']

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Статистика outbox сообщений"""
        from django.db.models import Count, Q

        stats = {
            'total': OutboxMessage.objects.count(),
            'by_status': dict(OutboxMessage.objects
                              .values('status')
                              .annotate(count=Count('id'))
                              .values_list('status', 'count')),
            'by_method': dict(OutboxMessage.objects
                              .values('method')
                              .annotate(count=Count('id'))
                              .values_list('method', 'count')),
            'pending_count': OutboxMessage.objects.filter(status='PENDING').count(),
            'failed_count': OutboxMessage.objects.filter(status='FAILED').count(),
        }

        return Response(stats)


class SystemViewSet(viewsets.ViewSet):
    """Системные endpoints для мониторинга"""

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Статистика системы"""
        from django.db.models import Count, Q

        stats = {
            'total_notifications': Notification.objects.count(),
            'sent_notifications': Notification.objects.filter(is_sent=True).count(),
            'pending_notifications': Notification.objects.filter(is_sent=False).count(),
            'outbox_messages': OutboxMessage.objects.count(),
            'outbox_by_status': dict(OutboxMessage.objects
                                     .values('status')
                                     .annotate(count=Count('id'))
                                     .values_list('status', 'count')),
            'outbox_by_method': dict(OutboxMessage.objects
                                     .values('method')
                                     .annotate(count=Count('id'))
                                     .values_list('method', 'count')),
        }

        return Response(stats)

    @action(detail=False, methods=['post'])
    def trigger_processing(self, request):
        """Принудительный запуск обработки"""
        result = process_pending_outbox_messages.delay()
        return Response({
            'task_id': str(result.id),
            'status': 'processing_triggered'
        })

    @action(detail=False, methods=['get'])
    def health(self, request):
        """Health check endpoint"""

        try:
            connection.ensure_connection()
            db_status = 'healthy'
        except Exception:
            db_status = 'unhealthy'

        try:
            cache.set('health_check', 'ok', 1)
            redis_status = 'healthy'
        except Exception:
            redis_status = 'unhealthy'

        return Response({
            'status': 'healthy' if db_status == 'healthy' and redis_status == 'healthy' else 'degraded',
            'database': db_status,
            'redis': redis_status,
            'timestamp': timezone.now().isoformat()
        })