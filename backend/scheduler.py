"""
Планировщик автоматического обновления расписания
Использует APScheduler для периодических задач
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ScheduleScheduler:
    """
    Планировщик для автоматического обновления расписания.
    
    Задачи:
    - Обновление HTML расписания каждые 3 часа
    - Проверка новых PDF файлов каждые 6 часов
    - Очистка устаревших данных ежедневно
    - Отправка уведомлений об изменениях
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db = None
    
    def start(self, db: Any):
        """Запуск планировщика"""
        self.db = db
        
        # Обновление HTML расписания каждые 3 часа
        self.scheduler.add_job(
            self.update_html_schedule,
            IntervalTrigger(hours=3),
            id='html_update',
            name='Обновление HTML расписания',
            replace_existing=True,
        )
        
        # Проверка PDF файлов каждые 6 часов
        self.scheduler.add_job(
            self.update_pdf_schedule,
            IntervalTrigger(hours=6),
            id='pdf_update',
            name='Обновление PDF расписания',
            replace_existing=True,
        )
        
        # Очистка устаревших данных каждый день в 3:00
        self.scheduler.add_job(
            self.cleanup_old_data,
            IntervalTrigger(hours=24),
            id='cleanup',
            name='Очистка устаревших данных',
            replace_existing=True,
        )
        
        # Проверка изменений и отправка уведомлений каждый час
        self.scheduler.add_job(
            self.check_and_notify,
            IntervalTrigger(hours=1),
            id='notifications',
            name='Проверка изменений и уведомления',
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Планировщик запущен")
    
    def stop(self):
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Планировщик остановлен")
    
    async def update_html_schedule(self):
        """Обновление расписания из HTML источника"""
        try:
            from parsers.html_parser import HTMLScheduleParser
            
            logger.info("Начало обновления HTML расписания...")
            
            async with HTMLScheduleParser() as parser:
                data = await parser.parse()
                if data:
                    self.db.update_schedule(data)
                    self.db.set_update_status(
                        success=True,
                        source="HTML парсер",
                        last_update=datetime.now().isoformat()
                    )
                    logger.info(f"HTML расписание обновлено: {len(data)} групп")
                else:
                    logger.warning("HTML парсер вернул пустые данные")
                    
        except Exception as e:
            logger.error(f"Ошибка обновления HTML расписания: {e}")
            self.db.set_update_status(success=False, source="HTML парсер")
    
    async def update_pdf_schedule(self):
        """Обновление расписания из PDF файлов"""
        try:
            from parsers.pdf_parser import PDFScheduleParser
            
            logger.info("Начало обновления PDF расписания...")
            
            async with PDFScheduleParser() as parser:
                data = await parser.parse()
                if data:
                    self.db.update_schedule(data)
                    self.db.set_update_status(
                        success=True,
                        source="PDF парсер",
                        last_update=datetime.now().isoformat()
                    )
                    logger.info(f"PDF расписание обновлено: {len(data)} групп")
                else:
                    logger.warning("PDF парсер вернул пустые данные")
                    
        except Exception as e:
            logger.error(f"Ошибка обновления PDF расписания: {e}")
            self.db.set_update_status(success=False, source="PDF парсер")
    
    async def cleanup_old_data(self):
        """Очистка устаревших данных"""
        try:
            logger.info("Очистка устаревших данных...")
            self.db.cleanup_old_schedules()
            logger.info("Очистка завершена")
        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}")
    
    async def check_and_notify(self):
        """Проверка изменений и отправка уведомлений"""
        try:
            changes = self.db.get_recent_changes()
            if changes:
                logger.info(f"Обнаружено {len(changes)} изменений")
                
                # Получение подписок
                subscriptions = self.db.get_subscriptions()
                
                for change in changes:
                    # Отправка уведомлений подписанным пользователям
                    for sub in subscriptions:
                        if sub['group_id'] == change['group_id']:
                            await self._send_notification(sub, change)
                            
        except Exception as e:
            logger.error(f"Ошибка проверки изменений: {e}")
    
    async def _send_notification(self, subscription: dict, change: dict):
        """Отправка уведомления через Telegram Bot API"""
        try:
            import aiohttp
            
            bot_token = "YOUR_BOT_TOKEN"  # Заменить на реальный токен
            chat_id = subscription['chat_id']
            
            message = self._format_notification(change)
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                await session.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                })
                
            logger.info(f"Уведомление отправлено: chat_id={chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
    
    def _format_notification(self, change: dict) -> str:
        """Форматирование текста уведомления"""
        emoji = "📅"
        
        if change.get('type') == 'cancelled':
            emoji = "❌"
            text = f"{emoji} <b>Пара отменена!</b>\n\n"
            text += f"📚 {change['subject']}\n"
            text += f"📅 {change['date']} ({change['dayOfWeek']})\n"
            text += f"⏰ {change['startTime']} - {change['endTime']}"
        elif change.get('type') == 'changed':
            emoji = "🔄"
            text = f"{emoji} <b>Изменение в расписании!</b>\n\n"
            text += f"📚 {change['subject']}\n"
            text += f"📅 {change['date']} ({change['dayOfWeek']})\n"
            if change.get('new_room'):
                text += f"📍 Новая аудитория: {change['new_room']}\n"
            if change.get('new_teacher'):
                text += f"👤 Новый преподаватель: {change['new_teacher']}\n"
            if change.get('comment'):
                text += f"\n💬 {change['comment']}"
        else:
            emoji = "🆕"
            text = f"{emoji} <b>Обновление расписания</b>\n\n"
            text += f"Расписание группы {change.get('group_name', '')} обновлено"
        
        return text
