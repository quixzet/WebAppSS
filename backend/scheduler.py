"""
Планировщик задач для автоматического обновления расписания.

Использует APScheduler для:
- Автоматического парсинга расписания каждые 24 часа (в 3:00 ночи)
- Проверки необходимости обновления при запуске
- Логирования всех операций

Задачи:
- parse_schedule: основной парсинг HTML + PDF
- cleanup_data: очистка устаревших данных
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Callable, Awaitable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger(__name__)


class ScheduleUpdater:
    """
    Планировщик обновления расписания.
    
    Управляет автоматическим парсингом расписания с сайта СИЭУиП.
    Поддерживает:
    - Запуск по расписанию (каждый день в 3:00)
    - Ручной запуск (по запросу)
    - Проверку необходимости обновления
    - Уведомления о результатах
    """
    
    def __init__(
        self,
        parse_callback: Callable[[], Awaitable[dict]],
        cleanup_callback: Optional[Callable[[], Awaitable[None]]] = None,
        notification_callback: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        """
        Args:
            parse_callback: Асинхронная функция парсинга расписания
            cleanup_callback: Асинхронная функция очистки данных
            notification_callback: Функция отправки уведомлений об изменениях
        """
        self.parse_callback = parse_callback
        self.cleanup_callback = cleanup_callback
        self.notification_callback = notification_callback
        self.scheduler = AsyncIOScheduler(
            timezone="Europe/Moscow",
            job_defaults={
                'coalesce': True,         # Объединять пропущенные запуски
                'max_instances': 1,        # Только один экземпляр задачи
                'misfire_grace_time': 3600  # Допуск пропуска 1 час
            }
        )
        self._is_running = False
        self._last_result: Optional[dict] = None
    
    def start(self):
        """
        Запуск планировщика.
        
        Настраивает задачи:
        1. Ежедневный парсинг в 3:00 по Москве
        2. Еженедельная очистка данных (воскресенье в 4:00)
        3. Подписывается на события выполнения задач
        """
        if self._is_running:
            logger.warning("Планировщик уже запущен")
            return
        
        # Задача 1: Ежедневный парсинг в 3:00
        self.scheduler.add_job(
            self._scheduled_parse,
            CronTrigger(hour=3, minute=0),
            id='daily_schedule_parse',
            name='Ежедневный парсинг расписания',
            replace_existing=True,
            misfire_grace_time=3600
        )
        
        # Задача 2: Еженедельная очистка (воскресенье в 4:00)
        if self.cleanup_callback:
            self.scheduler.add_job(
                self._scheduled_cleanup,
                CronTrigger(day_of_week='sun', hour=4, minute=0),
                id='weekly_cleanup',
                name='Еженедельная очистка данных',
                replace_existing=True
            )
        
        # Задача 3: Проверка каждые 6 часов (на случай пропуска)
        self.scheduler.add_job(
            self._check_and_parse_if_needed,
            IntervalTrigger(hours=6),
            id='check_update_needed',
            name='Проверка необходимости обновления',
            replace_existing=True
        )
        
        # Подписка на события
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        
        self.scheduler.start()
        self._is_running = True
        
        logger.info("Планировщик запущен")
        logger.info("  - Ежедневный парсинг: каждый день в 03:00")
        logger.info("  - Проверка обновления: каждые 6 часов")
        if self.cleanup_callback:
            logger.info("  - Очистка данных: каждое воскресенье в 04:00")
    
    def stop(self):
        """Остановка планировщика"""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("Планировщик остановлен")
    
    async def trigger_manual_update(self) -> dict:
        """
        Ручной запуск обновления расписания.
        
        Вызывается через POST /api/refresh
        
        Returns:
            Результат парсинга
        """
        logger.info("Ручной запуск обновления расписания")
        
        try:
            result = await self.parse_callback()
            self._last_result = result
            
            # Отправляем уведомления об изменениях
            if self.notification_callback and result.get('success'):
                try:
                    await self.notification_callback(result)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомлений: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Ошибка ручного обновления: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _scheduled_parse(self):
        """Задача ежедневного парсинга (вызывается планировщиком)"""
        logger.info("=" * 60)
        logger.info("Запуск планового парсинга расписания")
        logger.info("=" * 60)
        
        try:
            result = await self.parse_callback()
            self._last_result = result
            
            if result.get('success'):
                logger.info(
                    f"✅ Парсинг завершён успешно: "
                    f"{result.get('lessons_count', 0)} занятий, "
                    f"{result.get('groups_count', 0)} групп, "
                    f"{result.get('pdf_files_count', 0)} PDF файлов"
                )
                
                # Отправляем уведомления
                if self.notification_callback:
                    try:
                        await self.notification_callback(result)
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомлений: {e}")
            else:
                logger.error(
                    f"❌ Парсинг завершён с ошибкой: {result.get('error', 'неизвестно')}"
                )
        
        except Exception as e:
            logger.error(f"❌ Критическая ошибка парсинга: {e}", exc_info=True)
            self._last_result = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _scheduled_cleanup(self):
        """Задача еженедельной очистки данных"""
        logger.info("Запуск плановой очистки данных")
        
        if self.cleanup_callback:
            try:
                await self.cleanup_callback()
                logger.info("✅ Очистка данных завершена")
            except Exception as e:
                logger.error(f"❌ Ошибка очистки данных: {e}")
    
    async def _check_and_parse_if_needed(self):
        """
        Проверка необходимости обновления.
        
        Если данные устарели (старше 24 часов) или обновление не удавалось,
        запускает парсинг.
        """
        logger.debug("Проверка необходимости обновления...")
        
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from database import Database
        
        db = Database()
        
        if db.needs_update():
            logger.info("Данные устарели или отсутствуют — запускаем парсинг")
            await self._scheduled_parse()
        else:
            update_info = db.get_last_update()
            logger.debug(
                f"Данные актуальны. "
                f"Последнее обновление: {update_info.get('lastUpdate')}"
            )
    
    def _on_job_executed(self, event):
        """Обработчик успешного выполнения задачи"""
        logger.debug(f"Задача выполнена: {event.job_id}")
    
    def _on_job_error(self, event):
        """Обработчик ошибки выполнения задачи"""
        logger.error(
            f"Ошибка задачи {event.job_id}: "
            f"{event.exception}"
        )
    
    def get_status(self) -> dict:
        """Получение статуса планировщика"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None,
            })
        
        return {
            'is_running': self._is_running,
            'jobs': jobs,
            'last_result': self._last_result,
        }
    
    @property
    def last_result(self) -> Optional[dict]:
        """Последний результат парсинга"""
        return self._last_result


# ========================================
# Глобальный экземпляр планировщика
# ========================================

_updater: Optional[ScheduleUpdater] = None


def get_updater() -> Optional[ScheduleUpdater]:
    """Получить глобальный экземпляр планировщика"""
    return _updater


def init_updater(
    parse_callback: Callable,
    cleanup_callback: Optional[Callable] = None,
    notification_callback: Optional[Callable] = None,
) -> ScheduleUpdater:
    """
    Инициализация глобального планировщика.
    
    Вызывается при старте приложения.
    """
    global _updater
    _updater = ScheduleUpdater(
        parse_callback=parse_callback,
        cleanup_callback=cleanup_callback,
        notification_callback=notification_callback,
    )
    return _updater
