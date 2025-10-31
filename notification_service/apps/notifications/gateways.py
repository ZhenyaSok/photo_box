import logging
import os

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class EmailGateway:
    """Сервис отправки через email"""
    def send(self, notification, payload):
        try:
            recipient_email = payload.get('to_email', 'kapitan_kub@mail.ru')
            subject = payload.get('subject', notification.title)
            message = payload.get('message', notification.message)

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False,
            )

            return True

        except Exception:
            return False


class TelegramGateway:
    """Сервис отправки через ТГ"""
    def send(self, notification, payload):
        try:
            chat_id = os.getenv("CHAT_ID")
            message = payload.get('message')

            if not chat_id:
                return False

            bot_token = settings.TELEGRAM_BOT_TOKEN
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            response = requests.post(url, json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }, timeout=10)

            success = response.status_code == 200
            return success

        except Exception:
            return False

class SMSGateway:
    """Сервис отправки SMS через SMS.ru"""

    def send(self, notification, payload):
        try:
            phone = payload.get('phone')
            message = payload.get('message', notification.message)

            if not phone:
                logger.error("Номер телефона не указан в SMS payload")
                return False

            formatted_phone = self._format_phone(phone)

            response = requests.post(
                settings.SMS_API_URL,
                data={
                    'api_id': settings.SMS_API_ID,
                    'to': formatted_phone,
                    'msg': message,
                    'json': 1,
                    'from': settings.SMS_FROM
                },
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()

                if result.get('status') == 'OK':
                    sms_data = result.get('sms', {})
                    phone_data = sms_data.get(formatted_phone, {})

                    if phone_data.get('status') == 'OK':
                        logger.info(
                            "SMS успешно отправлено",
                            extra={
                                'phone': formatted_phone,
                                'sms_id': phone_data.get('sms_id'),
                                'cost': phone_data.get('cost'),
                                'notification_id': str(notification.id)
                            }
                        )
                        return True
                    else:
                        error_msg = phone_data.get('status_text', 'Неизвестная ошибка')
                        logger.error(
                            "Ошибка доставки SMS",
                            extra={
                                'phone': formatted_phone,
                                'error': error_msg,
                                'notification_id': str(notification.id)
                            }
                        )
                        return False
                else:
                    error_msg = result.get('status_text', 'Неизвестная ошибка')
                    logger.error(
                        "Ошибка SMS.ru API",
                        extra={
                            'phone': formatted_phone,
                            'error': error_msg,
                            'notification_id': str(notification.id)
                        }
                    )
                    return False
            else:
                logger.error(
                    "HTTP ошибка от SMS.ru",
                    extra={
                        'phone': formatted_phone,
                        'status_code': response.status_code,
                        'notification_id': str(notification.id)
                    }
                )
                return False

        except requests.exceptions.Timeout:
            logger.error(
                "Таймаут подключения к SMS.ru",
                extra={
                    'phone': payload.get('phone'),
                    'notification_id': str(notification.id)
                }
            )
            return False
        except requests.exceptions.ConnectionError:
            logger.error(
                "Ошибка подключения к SMS.ru",
                extra={
                    'phone': payload.get('phone'),
                    'notification_id': str(notification.id)
                }
            )
            return False
        except Exception as e:
            logger.error(
                "Неожиданная ошибка при отправке SMS",
                extra={
                    'phone': payload.get('phone'),
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'notification_id': str(notification.id)
                },
                exc_info=True
            )
            return False

    def _format_phone(self, phone):
        cleaned = ''.join(filter(str.isdigit, phone))

        if cleaned.startswith('89') and len(cleaned) == 11:
            cleaned = '+7' + cleaned[1:]

        if cleaned.startswith('79') and len(cleaned) == 11:
            cleaned = '+' + cleaned

        return cleaned


class DeliveryService:
    """Сервис доставки"""
    def __init__(self):
        self.gateways = {
            'EMAIL': EmailGateway(),
            'SMS': SMSGateway(),
            'TELEGRAM': TelegramGateway(),
        }

    def send_via_method(self, method, notification, payload):
        gateway = self.gateways.get(method)
        if not gateway:
            return False
        return gateway.send(notification, payload)