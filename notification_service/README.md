 Notification Service

Микросервис для отправки уведомлений через SMS, Telegram и Email с автоматическим fallback и гарантированной доставкой.

## 🎯 Бизнес-логика

### Fallback-цепочка
SMS → Telegram → Email

text

**Принцип работы:**
1. Система пытается отправить через **SMS** (3 попытки)
2. Если SMS не сработало → переходит к **Telegram** (3 попытки)  
3. Если Telegram не сработало → переходит к **Email** (3 попытки)
4. При первой успешной отправке уведомление помечается как доставленное

### Гарантии доставки
- ✅ **Outbox-паттерн** - сообщения не теряются при сбоях
- ✅ **Повторные попытки** - 3 попытки для каждого метода
- ✅ **Автоматический fallback** - переход к следующему методу при неудаче
- ✅ **Блокировки БД** - предотвращение дублирующей обработки
- ✅ **Восстановление зависших сообщений** - автоматический перезапуск

## 🚀 Быстрый старт

### 1. Установка и запуск
```bash
# Активация окружения
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```
# ENV
Создайте .env на основе .env-example

# Установка зависимостей
pip install -r requirements.txt

# Миграции БД
python manage.py migrate

# Запуск сервисов для windows (в разных терминалах)
redis-server
celery -A config worker --pool=solo --loglevel=info
celery -A config beat --loglevel=info
python manage.py runserver

# Запуск проекта с помощью Docker

## Предварительные требования

- Установленный Docker
- Установленный Docker Compose


```bash
docker-compose build
docker-compose up -d
```
#  Сервисы
Приложение будет доступно по адресу:

- Основное приложение: http://localhost:8000
- База данных: PostgreSQL на порту 5432
- Кеш: Redis на порту 6379
- Celery worker: Фоновые задачи
- Celery beat: Периодические задачи

2. Создание уведомления
```bash
curl -X POST http://localhost:8000/api/notifications/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "title": "Важное уведомление",
    "message": "Проверьте ваш аккаунт",
    "delivery_methods": ["SMS", "TELEGRAM", "EMAIL"]
  }'
 ```
- Ответ:

```bash
json
{
  "id": 1,
  "status": "created"
}
```
#  📡 API Endpoints
Создание уведомления

POST /api/notifications/
```bash
Content-Type: application/json

{
  "user_id": 1,
  "title": "string",
  "message": "string", 
  "delivery_methods": ["SMS", "TELEGRAM", "EMAIL"]
}
```
Получение уведомлений

GET /api/notifications/          # Список всех уведомлений
GET /api/notifications/{id}/     # Конкретное уведомление