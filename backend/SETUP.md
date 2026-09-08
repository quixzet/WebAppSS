# Инструкция по запуску backend

## Быстрый старт

```bash
# 1. Перейти в директорию backend
cd backend

# 2. Создать виртуальное окружение (рекомендуется)
python -m venv venv

# Активировать venv:
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Запустить сервер
python main.py
```

Сервер будет доступен по адресу: http://localhost:8000

Документация API: http://localhost:8000/docs

## Что происходит при запуске

1. **Инициализация БД** — создаётся файл `schedule.db` с таблицами
2. **Запуск планировщика** — APScheduler начинает работу
3. **Проверка данных** — если данных нет, автоматически запускается парсинг
4. **Парсинг расписания** — загружается https://sielom.ru/schedule, извлекаются PDF файлы, парсятся

## Проверка работоспособности

```bash
# Проверить health
curl http://localhost:8000/api/health

# Получить список групп
curl http://localhost:8000/api/groups

# Получить статус обновления
curl http://localhost:8000/api/last-update

# Ручной запуск обновления
curl -X POST http://localhost:8000/api/refresh
```

## Логи

Все логи выводятся в консоль с временными метками:

```
2026-09-09 12:00:00 [INFO] main: 🚀 Запуск приложения расписания СИЭУиП
2026-09-09 12:00:01 [INFO] database: База данных инициализирована успешно
2026-09-09 12:00:01 [INFO] scheduler: Планировщик запущен
2026-09-09 12:00:02 [INFO] parsers.html_parser: Начало парсинга HTML страницы
2026-09-09 12:00:05 [INFO] parsers.html_parser: Найдено 25 PDF источников расписания
```

## Структура проекта

```
backend/
├── main.py              # FastAPI приложение
├── database.py          # SQLite база данных
├── scheduler.py         # APScheduler планировщик
├── parsers/
│   ├── html_parser.py   # Парсер HTML страницы
│   └── pdf_parser.py    # Парсер PDF файлов
├── requirements.txt     # Зависимости
└── README.md           # Документация
```

## API Endpoints

### GET /api/groups
Список всех групп

**Ответ:**
```json
[
  {
    "id": "grp_ис-201_a1b2c3",
    "name": "ИС-201",
    "specialty": "Информационные системы",
    "education_form": "Очная",
    "building": "Корпус №5"
  }
]
```

### GET /api/schedule/{group_id}
Расписание группы

**Ответ:**
```json
{
  "days": [
    {
      "dayOfWeek": "Понедельник",
      "lessons": [
        {
          "id": "grp_ис-201_a1b2c3_Понедельник_1",
          "number": 1,
          "startTime": "08:30",
          "endTime": "10:00",
          "subject": "Базы данных",
          "type": "lecture",
          "teacher": "Иванов И.И.",
          "room": "305",
          "building": "Корпус №5",
          "isChanged": false,
          "comment": ""
        }
      ]
    }
  ]
}
```

### GET /api/last-update
Информация о последнем обновлении

**Ответ:**
```json
{
  "lastUpdate": "2026-09-09T03:00:00",
  "lastAttempt": "2026-09-09T03:00:00",
  "nextScheduled": "2026-09-10T03:00:00",
  "source": "sielom.ru/schedule",
  "success": true,
  "errorMessage": "",
  "lessonsCount": 1250,
  "groupsCount": 45,
  "pdfFilesCount": 25
}
```

### POST /api/refresh
Ручной запуск обновления

**Ответ:**
```json
{
  "success": true,
  "message": "Обновление запущено в фоновом режиме...",
  "timestamp": "2026-09-09T12:00:00"
}
```

## Настройка Telegram уведомлений

1. Создайте бота через @BotFather
2. Получите токен бота
3. В файле `main.py` установите токен:
   ```python
   BOT_TOKEN = "your_bot_token_here"
   ```
4. Пользователи могут подписаться через:
   ```bash
   POST /api/notifications/subscribe
   {
     "chat_id": "123456789",
     "group_id": "grp_ис-201_a1b2c3"
   }
   ```

## Troubleshooting

### Ошибка: "Не удалось загрузить HTML страницу"
- Проверьте доступность сайта https://sielom.ru/schedule
- Проверьте интернет-соединение
- Попробуйте ручной запуск: `POST /api/refresh`

### Ошибка: "На странице не найдено PDF файлов"
- Возможно, изменилась структура HTML страницы
- Проверьте логи для деталей
- Обновите парсер в `parsers/html_parser.py`

### База данных заблокирована
- Убедитесь, что только один экземпляр приложения запущен
- Удалите файл `schedule.db` для сброса

## Производительность

- Парсинг всех PDF файлов: ~2-5 минут
- Размер БД после парсинга: ~5-10 МБ
- Время ответа API: <100 мс
- Потребление памяти: ~100-200 МБ

## Безопасность

- CORS настроен на `*` (разрешить все источники)
- Для продакшена укажите конкретные домены:
  ```python
  allow_origins=["https://your-domain.com"]
  ```
- Добавьте аутентификацию для `POST /api/refresh`
- Используйте переменные окружения для секретов
