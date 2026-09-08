"""
Модуль работы с базой данных
Использует SQLite для хранения расписания и настроек
"""

import sqlite3
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """
    Управление базой данных расписания.
    
    Таблицы:
    - groups: список групп
    - schedules: расписание занятий
    - update_status: статус обновления
    - subscriptions: подписки на уведомления
    - changes: журнал изменений
    """
    
    def __init__(self, db_path: str = "schedule.db"):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка БД: {e}")
            raise
        finally:
            conn.close()
    
    def initialize(self):
        """Инициализация базы данных (создание таблиц)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    faculty TEXT,
                    course INTEGER
                )
            ''')
            
            # Таблица расписания
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    lesson_number INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    subject TEXT,
                    lesson_type TEXT,
                    teacher TEXT,
                    room TEXT,
                    building TEXT,
                    is_changed BOOLEAN DEFAULT 0,
                    comment TEXT,
                    week_number INTEGER,
                    updated_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # Таблица статуса обновления
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS update_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_update TEXT,
                    next_update TEXT,
                    source TEXT,
                    success BOOLEAN DEFAULT 1
                )
            ''')
            
            # Таблица подписок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    notification_types TEXT DEFAULT '["changes", "cancellations"]',
                    created_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # Таблица изменений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    date TEXT,
                    day_of_week TEXT,
                    lesson_number INTEGER,
                    change_type TEXT,
                    subject TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    comment TEXT,
                    detected_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # Индексы для быстрого поиска
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_schedules_group_date
                ON schedules(group_id, date)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_subscriptions_group
                ON subscriptions(group_id)
            ''')
            
            logger.info("База данных инициализирована")
    
    def get_all_groups(self) -> List[Dict]:
        """Получение списка всех групп"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups ORDER BY name')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_schedule(self, group_id: str, week: Optional[int] = None) -> Optional[Dict]:
        """Получение расписания группы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Определение номера недели
            if week is None:
                week = self._get_current_week_number()
            
            cursor.execute('''
                SELECT * FROM schedules
                WHERE group_id = ? AND week_number = ?
                ORDER BY date, lesson_number
            ''', (group_id, week))
            
            rows = cursor.fetchall()
            if not rows:
                return None
            
            # Группировка по дням
            days = {}
            for row in rows:
                date = row['date']
                if date not in days:
                    days[date] = {
                        'date': date,
                        'dayOfWeek': row['day_of_week'],
                        'lessons': []
                    }
                
                days[date]['lessons'].append({
                    'id': row['id'],
                    'number': row['lesson_number'],
                    'startTime': row['start_time'],
                    'endTime': row['end_time'],
                    'subject': row['subject'],
                    'type': row['lesson_type'],
                    'teacher': row['teacher'],
                    'room': row['room'],
                    'building': row['building'],
                    'isChanged': bool(row['is_changed']),
                    'comment': row['comment'],
                })
            
            return {
                'weekNumber': week,
                'days': list(days.values())
            }
    
    def update_schedule(self, data: List[Dict]):
        """Обновление расписания из данных парсера"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            for group_data in data:
                group_name = group_data.get('group', '')
                week_data = group_data.get('week', {})
                days = week_data.get('days', [])
                
                # Поиск или создание группы
                cursor.execute('SELECT id FROM groups WHERE name = ?', (group_name,))
                group_row = cursor.fetchone()
                
                if group_row:
                    group_id = group_row['id']
                else:
                    group_id = f"group_{hash(group_name) % 10000}"
                    cursor.execute(
                        'INSERT OR REPLACE INTO groups (id, name) VALUES (?, ?)',
                        (group_id, group_name)
                    )
                
                week_number = self._get_current_week_number()
                
                for day in days:
                    for lesson in day.get('lessons', []):
                        lesson_id = f"{group_id}_{day['date']}_{lesson['number']}"
                        
                        # Проверка на изменения
                        cursor.execute(
                            'SELECT * FROM schedules WHERE id = ?',
                            (lesson_id,)
                        )
                        existing = cursor.fetchone()
                        
                        is_changed = False
                        if existing:
                            is_changed = self._detect_changes(existing, lesson)
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO schedules
                            (id, group_id, date, day_of_week, lesson_number,
                             start_time, end_time, subject, lesson_type,
                             teacher, room, building, is_changed, comment,
                             week_number, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            lesson_id, group_id, day.get('date', ''),
                            day.get('dayOfWeek', ''), lesson.get('number', 0),
                            lesson.get('startTime', ''), lesson.get('endTime', ''),
                            lesson.get('subject', ''), lesson.get('type', 'practice'),
                            lesson.get('teacher', ''), lesson.get('room', ''),
                            lesson.get('building', ''), is_changed,
                            lesson.get('comment', ''), week_number, now
                        ))
    
    def _detect_changes(self, existing: sqlite3.Row, new_lesson: Dict) -> bool:
        """Обнаружение изменений в занятии"""
        changes = []
        
        if existing['room'] != new_lesson.get('room', ''):
            changes.append(('room', existing['room'], new_lesson.get('room', '')))
        if existing['teacher'] != new_lesson.get('teacher', ''):
            changes.append(('teacher', existing['teacher'], new_lesson.get('teacher', '')))
        if existing['subject'] != new_lesson.get('subject', ''):
            changes.append(('subject', existing['subject'], new_lesson.get('subject', '')))
        
        return len(changes) > 0
    
    def get_update_status(self) -> Dict:
        """Получение статуса последнего обновления"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM update_status WHERE id = 1')
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            
            return {
                'lastUpdate': datetime.now().isoformat(),
                'nextUpdate': (datetime.now() + timedelta(hours=3)).isoformat(),
                'source': 'Инициализация',
                'success': True,
            }
    
    def set_update_status(self, success: bool, source: str = "", last_update: str = None):
        """Установка статуса обновления"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = last_update or datetime.now().isoformat()
            next_update = (datetime.now() + timedelta(hours=3)).isoformat()
            
            cursor.execute('''
                INSERT OR REPLACE INTO update_status (id, last_update, next_update, source, success)
                VALUES (1, ?, ?, ?, ?)
            ''', (now, next_update, source, success))
    
    def add_subscription(self, chat_id: str, group_id: str):
        """Добавление подписки на уведомления"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO subscriptions (chat_id, group_id, created_at)
                VALUES (?, ?, ?)
            ''', (chat_id, group_id, datetime.now().isoformat()))
    
    def remove_subscription(self, chat_id: str):
        """Удаление подписки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM subscriptions WHERE chat_id = ?', (chat_id,))
    
    def get_subscriptions(self) -> List[Dict]:
        """Получение всех подписок"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM subscriptions')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_changes(self) -> List[Dict]:
        """Получение недавних изменений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM changes
                WHERE detected_at > datetime('now', '-1 hour')
                ORDER BY detected_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_schedules(self):
        """Очистка расписаний старше 2 недель"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(weeks=2)).isoformat()
            cursor.execute('DELETE FROM schedules WHERE updated_at < ?', (cutoff,))
            deleted = cursor.rowcount
            logger.info(f"Удалено {deleted} устаревших записей")
    
    def _get_current_week_number(self) -> int:
        """Получение номера текущей учебной недели"""
        # Упрощённый расчёт - в реальности нужно учитывать начало семестра
        now = datetime.now()
        year_start = datetime(now.year, 9, 1)  # Начало учебного года
        if now < year_start:
            year_start = datetime(now.year - 1, 9, 1)
        
        delta = now - year_start
        return delta.days // 7 + 1
