# Backend API — Расписание занятий

## Структура проекта

```
backend/
├── main.py              # FastAPI приложение
├── parsers/
│   ├── html_parser.py   # Парсинг HTML расписания
│   └── pdf_parser.py    # Парсинг PDF расписания
├── scheduler.py         # APScheduler для автообновления
├── database.py          # SQLite/PostgreSQL база данных
└── requirements.txt     # Зависимости Python
```

## API Endpoints

### GET /api/groups
Список всех групп.

**Response:**
```json
[
  {
    "id": "1",
    "name": "ИСП-21-1",
    "faculty": "Информационные системы",
    "course": 3
  }
]
```

### GET /api/schedule/{group_id}
Расписание указанной группы на текущую неделю.

**Response:**
```json
{
  "weekNumber": 1,
  "days": [
    {
      "date": "2024-01-15",
      "dayOfWeek": "Понедельник",
      "lessons": [
        {
          "id": "1-1",
          "number": 1,
          "startTime": "08:30",
          "endTime": "10:00",
          "subject": "Базы данных",
          "type": "lecture",
          "teacher": "Иванов А.П.",
          "room": "301",
          "building": "Главный корпус",
          "isChanged": false
        }
      ]
    }
  ]
}
```

### GET /api/updates
Статус последнего обновления данных.

**Response:**
```json
{
  "lastUpdate": "2024-01-15T10:30:00Z",
  "nextUpdate": "2024-01-15T13:30:00Z",
  "source": "Сайт института",
  "success": true
}
```

### POST /api/notifications/subscribe
Подписка на уведомления об изменениях (для Telegram Bot).

**Request:**
```json
{
  "chatId": "123456789",
  "groupId": "1",
  "types": ["changes", "cancellations"]
}
```

## Установка и запуск

```bash
pip install -r requirements.txt
python main.py
```

## Зависимости

```
fastapi==0.104.0
uvicorn==0.24.0
beautifulsoup4==4.12.2
pdfplumber==0.10.3
apscheduler==3.10.4
sqlalchemy==2.0.23
aiohttp==3.9.1
pydantic==2.5.0
```

## Интеграция с Telegram Bot

Для отправки уведомлений через Telegram Bot API:

```python
import aiohttp

async def send_telegram_notification(chat_id: str, message: str):
    bot_token = "YOUR_BOT_TOKEN"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        })
```

## Парсинг расписания

### HTML парсер
Парсит интерактивное расписание с сайта института:
- Загрузка страницы через aiohttp
- Извлечение данных через BeautifulSoup
- Нормализация и сохранение в БД

### PDF парсер
Обрабатывает PDF файлы с расписанием:
- Извлечение текста через pdfplumber
- Регулярные выражения для структурирования
- Сопоставление с группами и аудиториями

## Планировщик

APScheduler выполняет:
- Обновление HTML расписания каждые 3 часа
- Проверку новых PDF файлов каждые 6 часов
- Очистку устаревших данных раз в сутки
- Отправку уведомлений при обнаружении изменений
