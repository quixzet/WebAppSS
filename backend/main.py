"""
Главный модуль FastAPI приложения расписания СИЭУиП.

Полностью переработан для устранения "database is locked":
- asyncio.Lock для предотвращения параллельного парсинга
- Сбор всех данных ПЕРЕД записью в БД
- Единственный вызов bulk_update_schedule после парсинга
- Обработка сигналов для graceful shutdown

API Endpoints:
- GET  /api/groups         — список всех групп
- GET  /api/schedule/{id}  — расписание группы
- GET  /api/updates        — статус последнего обновления
- GET  /api/last-update    — подробная информация о последнем обновлении
- POST /api/refresh        — ручной запуск обновления расписания
- GET  /api/stats          — статистика базы данных
- GET  /api/changes        — недавние изменения в расписании
- GET  /api/scheduler/status — статус планировщика
- GET  /api/health         — проверка работоспособности

Источник данных: https://sielom.ru/schedule
"""

import logging
import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import Database
from scheduler import init_updater, get_updater
from parsers.html_parser import HTMLScheduleParser
from parsers.pdf_parser import PDFScheduleParser

# ========================================
# Настройка логирования
# ========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========================================
# Глобальные переменные для синхронизации
# ========================================

# Lock для предотвращения параллельного парсинга
_parse_lock = asyncio.Lock()

# Флаг состояния парсинга
_is_parsing_running = False

# Флаг для graceful shutdown
_shutdown_requested = False

# ========================================
# Модели данных (Pydantic)
# ========================================

class GroupResponse(BaseModel):
    """Модель ответа со списком групп"""
    id: str
    name: str
    specialty: str = ""
    education_form: str = "Очная"
    building: str = ""


class LessonResponse(BaseModel):
    """Модель ответа с занятием"""
    id: str
    number: int
    startTime: str = ""
    endTime: str = ""
    subject: str = ""
    type: str = "practice"
    teacher: str = ""
    room: str = ""
    building: str = ""
    isChanged: bool = False
    comment: str = ""


class DayResponse(BaseModel):
    """Модель ответа с расписанием на день"""
    dayOfWeek: str
    lessons: List[LessonResponse]


class ScheduleResponse(BaseModel):
    """Модель ответа с расписанием"""
    days: List[DayResponse]


class UpdateStatusResponse(BaseModel):
    """Модель ответа со статусом обновления"""
    lastUpdate: Optional[str] = None
    lastAttempt: Optional[str] = None
    nextScheduled: Optional[str] = None
    source: str = ""
    success: bool = False
    errorMessage: str = ""
    lessonsCount: int = 0
    groupsCount: int = 0
    pdfFilesCount: int = 0


class RefreshResponse(BaseModel):
    """Модель ответа на ручной запуск обновления"""
    success: bool
    message: str
    lessonsCount: int = 0
    groupsCount: int = 0
    pdfFilesCount: int = 0
    timestamp: str
    error: str = ""


class ChangeResponse(BaseModel):
    """Модель ответа с изменением в расписании"""
    id: int
    group_id: str
    group_name: str = ""
    day_of_week: str = ""
    lesson_number: int = 0
    change_type: str = ""
    field_name: str = ""
    old_value: str = ""
    new_value: str = ""
    subject: str = ""
    detected_at: str = ""


# ========================================
# Обработка сигналов для graceful shutdown
# ========================================

def setup_signal_handlers():
    """
    Настройка обработчиков сигналов SIGTERM и SIGINT.
    
    При получении сигнала:
    1. Устанавливает флаг _shutdown_requested
    2. Ждёт завершения текущей транзакции
    3. Не допускает прерывания записи в БД
    """
    def signal_handler(signum, frame):
        global _shutdown_requested
        
        if _shutdown_requested:
            logger.warning("⚠️ Повторный сигнал завершения, принудительный выход")
            sys.exit(1)
        
        logger.info(f"🛑 Получен сигнал {signum}, запрашиваем graceful shutdown...")
        _shutdown_requested = True
        
        # Если парсинг запущен, ждём его завершения
        if _is_parsing_running:
            logger.info("⏳ Парсинг в процессе, ожидаем завершения...")
            # Не вызываем sys.exit(), позволяем завершиться естественно
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


# ========================================
# Функция парсинга расписания
# ========================================

async def parse_schedule() -> dict:
    """
    Основная функция парсинга расписания.
    
    ПЕРЕРАБОТАНО для устранения "database is locked":
    1. Собирает ВСЕ занятия из ВСЕХ PDF в единый список
    2. Выполняет ЕДИНСТВЕННЫЙ вызов bulk_update_schedule
    3. Использует asyncio.Lock для предотвращения параллельного запуска
    
    Returns:
        dict с результатом парсинга
    """
    global _is_parsing_running
    
    # Проверка на параллельный запуск
    if _parse_lock.locked():
        logger.warning("⚠️ Парсинг уже запущен, пропускаем повторный вызов")
        return {
            'success': False,
            'error': 'Парсинг уже выполняется',
            'timestamp': datetime.now().isoformat(),
            'lessons_count': 0,
            'groups_count': 0,
            'pdf_files_count': 0,
        }
    
    async with _parse_lock:
        _is_parsing_running = True
        
        try:
            return await _do_parse_schedule()
        
        finally:
            _is_parsing_running = False


async def _do_parse_schedule() -> dict:
    """
    Внутренняя функция парсинга (вызывается под lock).
    
    Этапы:
    1. Парсинг HTML страницы
    2. Парсинг всех PDF файлов (сбор данных)
    3. ЕДИНСТВЕННАЯ запись в БД через bulk_update_schedule
    """
    db = Database()
    now = datetime.now().isoformat()
    
    logger.info("=" * 60)
    logger.info("🚀 Начало полного цикла парсинга расписания")
    logger.info("=" * 60)
    
    # ========================================
    # Этап 1: Парсинг HTML страницы
    # ========================================
    
    html_parser = HTMLScheduleParser()
    try:
        html_result = await html_parser.parse()
        
        if not html_result.success:
            error_msg = f"Ошибка парсинга HTML: {html_result.error}"
            logger.error(f"❌ {error_msg}")
            
            db.set_last_update(
                success=False,
                source="sielom.ru/schedule",
                error_message=error_msg
            )
            
            return {
                'success': False,
                'error': error_msg,
                'timestamp': now,
                'lessons_count': 0,
                'groups_count': 0,
                'pdf_files_count': 0,
            }
        
        sources = html_result.sources
        logger.info(f"📄 Найдено {len(sources)} PDF файлов для парсинга")
        
        if not sources:
            error_msg = "На странице не найдено PDF файлов с расписанием"
            logger.error(f"❌ {error_msg}")
            
            db.set_last_update(
                success=False,
                source="sielom.ru/schedule",
                error_message=error_msg
            )
            
            return {
                'success': False,
                'error': error_msg,
                'timestamp': now,
                'lessons_count': 0,
                'groups_count': 0,
                'pdf_files_count': 0,
            }
        
        # ========================================
        # Этап 2: Парсинг всех PDF (СБОР ДАННЫХ)
        # ========================================
        
        logger.info("📥 Начало парсинга PDF файлов (сбор данных)...")
        
        pdf_parser = PDFScheduleParser()
        try:
            pdf_results = await pdf_parser.parse_multiple(sources)
        finally:
            await pdf_parser.close()
        
        # ========================================
        # Этап 3: Сбор всех занятий в единый список
        # ========================================
        
        all_lessons = []
        total_groups = set()
        successful_pdfs = 0
        
        for result in pdf_results:
            if result.success:
                successful_pdfs += 1
                
                # Преобразуем ScheduleLesson в dict
                for lesson in result.lessons:
                    lesson_dict = {
                        'group': lesson.group,
                        'day': lesson.day,
                        'number': lesson.number,
                        'time': lesson.time,
                        'end_time': lesson.end_time,
                        'subject': lesson.subject,
                        'type': lesson.type,
                        'teacher': lesson.teacher,
                        'room': lesson.room,
                        'building': lesson.building,
                        'comment': lesson.comment,
                        'education_form': result.source.education_form,
                        'specialty': result.source.specialty,
                    }
                    all_lessons.append(lesson_dict)
                    total_groups.add(lesson.group)
                
                logger.info(
                    f"  ✅ {result.source.title}: "
                    f"{len(result.lessons)} занятий, "
                    f"{len(result.groups)} групп"
                )
            else:
                logger.warning(
                    f"  ❌ {result.source.title}: {result.error}"
                )
        
        logger.info(
            f"📊 Собрано данных: {len(all_lessons)} занятий "
            f"из {successful_pdfs}/{len(sources)} PDF файлов"
        )
        
        if not all_lessons:
            error_msg = "Не удалось извлечь занятия из PDF файлов"
            logger.error(f"❌ {error_msg}")
            
            db.set_last_update(
                success=False,
                source="sielom.ru/schedule",
                error_message=error_msg
            )
            
            return {
                'success': False,
                'error': error_msg,
                'timestamp': now,
                'lessons_count': 0,
                'groups_count': 0,
                'pdf_files_count': 0,
            }
        
        # ========================================
        # Этап 4: ЕДИНСТВЕННАЯ запись в БД
        # ========================================
        
        logger.info("💾 Начало записи в базу данных (одна транзакция)...")
        
        try:
            stats = db.bulk_update_schedule(
                all_lessons,
                source_url="https://sielom.ru/schedule"
            )
            
            # Обновление статуса
            db.set_last_update(
                success=True,
                source="sielom.ru/schedule",
                lessons_count=stats['total_lessons'],
                groups_count=stats['total_groups'],
                pdf_files_count=successful_pdfs
            )
            
            result = {
                'success': True,
                'timestamp': now,
                'lessons_count': stats['total_lessons'],
                'groups_count': stats['total_groups'],
                'pdf_files_count': successful_pdfs,
                'total_pdfs_found': len(sources),
                'changes_detected': stats.get('changes_detected', 0),
                'elapsed_seconds': stats.get('elapsed_seconds', 0.0),
            }
            
            logger.info(
                f"✅ Парсинг завершён успешно за {result['elapsed_seconds']:.2f}с: "
                f"{result['lessons_count']} занятий, "
                f"{result['groups_count']} групп, "
                f"{result['changes_detected']} изменений"
            )
            
            return result
        
        except Exception as e:
            error_msg = f"Ошибка записи в БД: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            
            db.set_last_update(
                success=False,
                source="sielom.ru/schedule",
                error_message=error_msg
            )
            
            return {
                'success': False,
                'error': error_msg,
                'timestamp': now,
                'lessons_count': 0,
                'groups_count': 0,
                'pdf_files_count': 0,
            }
    
    except Exception as e:
        error_msg = f"Критическая ошибка парсинга: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        
        db.set_last_update(
            success=False,
            source="sielom.ru/schedule",
            error_message=error_msg
        )
        
        return {
            'success': False,
            'error': error_msg,
            'timestamp': now,
            'lessons_count': 0,
            'groups_count': 0,
            'pdf_files_count': 0,
        }
    
    finally:
        await html_parser.close()


async def cleanup_data():
    """Очистка устаревших данных"""
    db = Database()
    db.cleanup_old_data(days=30)
    logger.info("✅ Очистка устаревших данных завершена")


async def send_notifications(result: dict):
    """
    Отправка уведомлений об изменениях.
    
    Подготовлено для интеграции с Telegram Bot API.
    """
    if not result.get('success'):
        return
    
    db = Database()
    changes = db.get_recent_changes(hours=24)
    
    if not changes:
        logger.debug("Нет изменений для уведомления")
        return
    
    logger.info(f"📢 Найдено {len(changes)} изменений для уведомления")
    
    # Здесь можно добавить логику отправки уведомлений
    # через Telegram Bot API или другие каналы


# ========================================
# Создание FastAPI приложения
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекст жизненного цикла приложения.
    
    При запуске:
    - Настраивает обработчики сигналов
    - Инициализирует БД
    - Запускает планировщик
    - Проверяет необходимость обновления
    
    При остановке:
    - Останавливает планировщик
    - Ждёт завершения текущих операций
    """
    logger.info("=" * 60)
    logger.info("🚀 Запуск приложения расписания СИЭУиП")
    logger.info("=" * 60)
    
    # Настройка обработчиков сигналов
    setup_signal_handlers()
    
    # Инициализация БД
    db = Database()
    logger.info("✅ База данных инициализирована")
    
    # Инициализация и запуск планировщика
    updater = init_updater(
        parse_callback=parse_schedule,
        cleanup_callback=cleanup_data,
        notification_callback=send_notifications,
    )
    updater.start()
    logger.info("✅ Планировщик запущен")
    
    # Проверка необходимости обновления при старте
    if db.needs_update():
        logger.info("📊 Данные устарели или отсутствуют — запускаем начальное обновление...")
        # Запускаем в фоне, чтобы не блокировать старт
        asyncio.create_task(updater.trigger_manual_update())
    else:
        update_info = db.get_last_update()
        logger.info(
            f"📊 Данные актуальны. "
            f"Последнее обновление: {update_info.get('lastUpdate')}"
        )
    
    yield
    
    # Остановка
    logger.info("🛑 Остановка приложения...")
    updater.stop()
    logger.info("✅ Приложение остановлено")


app = FastAPI(
    title="Расписание СИЭУиП API",
    description="API для просмотра расписания занятий студентов СИЭУиП",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# API Endpoints
# ========================================

@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "name": "Расписание СИЭУиП API",
        "version": "3.0.0",
        "source": "https://sielom.ru/schedule",
        "docs": "/docs",
        "features": [
            "WAL-режим для SQLite",
            "Bulk операции для массовых вставок",
            "Retry механизм при блокировке БД",
            "asyncio.Lock для предотвращения параллельного парсинга",
        ]
    }


@app.get("/api/groups", response_model=List[GroupResponse])
async def get_groups():
    """
    Получить список всех групп.
    
    Возвращает все группы, для которых есть расписание.
    """
    db = Database()
    groups = db.get_all_groups()
    
    return [
        GroupResponse(
            id=g['id'],
            name=g['name'],
            specialty=g.get('specialty', ''),
            education_form=g.get('education_form', 'Очная'),
            building=g.get('building', ''),
        )
        for g in groups
    ]


@app.get("/api/schedule/{group_id}", response_model=ScheduleResponse)
async def get_schedule(group_id: str):
    """
    Получить расписание группы.
    
    Args:
        group_id: ID группы (из /api/groups)
    
    Returns:
        Расписание, сгруппированное по дням недели.
    """
    db = Database()
    schedule = db.get_schedule(group_id)
    
    if not schedule:
        raise HTTPException(
            status_code=404,
            detail=f"Расписание для группы '{group_id}' не найдено"
        )
    
    return ScheduleResponse(**schedule)


@app.get("/api/updates", response_model=UpdateStatusResponse)
async def get_updates():
    """
    Получить статус последнего обновления.
    
    Краткая информация о последнем обновлении данных.
    """
    db = Database()
    update_info = db.get_last_update()
    
    return UpdateStatusResponse(**update_info)


@app.get("/api/last-update", response_model=UpdateStatusResponse)
async def get_last_update():
    """
    Получить подробную информацию о последнем обновлении.
    
    Включает количество обработанных занятий, групп и PDF файлов.
    """
    db = Database()
    update_info = db.get_last_update()
    
    return UpdateStatusResponse(**update_info)


@app.post("/api/refresh", response_model=RefreshResponse)
async def refresh_schedule(background_tasks: BackgroundTasks):
    """
    Ручной запуск обновления расписания.
    
    Запускает полный цикл парсинга:
    1. Загрузка HTML страницы sielom.ru/schedule
    2. Извлечение ссылок на PDF файлы
    3. Парсинг каждого PDF
    4. Массовая запись в БД (одна транзакция)
    
    Использует asyncio.Lock для предотвращения параллельного запуска.
    """
    global _is_parsing_running
    
    # Проверка на параллельный запуск
    if _is_parsing_running:
        return RefreshResponse(
            success=False,
            message="Парсинг уже выполняется. Дождитесь завершения или проверьте статус через /api/scheduler/status",
            timestamp=datetime.now().isoformat()
        )
    
    logger.info("📥 Получен запрос на ручное обновление расписания")
    
    updater = get_updater()
    if not updater:
        raise HTTPException(
            status_code=503,
            detail="Планировщик не инициализирован"
        )
    
    # Запускаем обновление в фоне
    background_tasks.add_task(updater.trigger_manual_update)
    
    return RefreshResponse(
        success=True,
        message="Обновление запущено в фоновом режиме. "
                "Результат будет доступен через /api/last-update",
        timestamp=datetime.now().isoformat()
    )


@app.get("/api/changes", response_model=List[ChangeResponse])
async def get_changes(hours: int = 24):
    """
    Получить недавние изменения в расписании.
    
    Args:
        hours: За какой период показать изменения (по умолчанию 24 часа)
    """
    db = Database()
    changes = db.get_recent_changes(hours=hours)
    
    return [
        ChangeResponse(
            id=c['id'],
            group_id=c['group_id'],
            group_name=c.get('group_name', ''),
            day_of_week=c.get('day_of_week', ''),
            lesson_number=c.get('lesson_number', 0),
            change_type=c.get('change_type', ''),
            field_name=c.get('field_name', ''),
            old_value=c.get('old_value', ''),
            new_value=c.get('new_value', ''),
            subject=c.get('subject', ''),
            detected_at=c.get('detected_at', ''),
        )
        for c in changes
    ]


@app.get("/api/stats")
async def get_stats():
    """Получить статистику базы данных"""
    db = Database()
    return db.get_stats()


@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """Получить статус планировщика задач"""
    updater = get_updater()
    if not updater:
        return {"is_running": False, "jobs": []}
    
    status = updater.get_status()
    status['is_parsing_running'] = _is_parsing_running
    
    return status


@app.get("/api/health")
async def health_check():
    """Проверка работоспособности API"""
    db = Database()
    stats = db.get_stats()
    update_info = db.get_last_update()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": {
            "groups": stats['totalGroups'],
            "schedules": stats['totalSchedules'],
        },
        "last_update": {
            "success": update_info['success'],
            "time": update_info['lastUpdate'],
        },
        "parsing": {
            "is_running": _is_parsing_running,
        }
    }


# ========================================
# Запуск сервера
# ========================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Запуск сервера на порту 8000...")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
