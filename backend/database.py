"""
Модуль работы с базой данных для приложения расписания.

Использует SQLite для хранения:
- Группы студентов
- Расписание занятий
- Статус последнего обновления
- Подписки на уведомления
- Журнал изменений

Таблицы:
- groups: список групп
- schedules: расписание занятий
- last_update: время последнего парсинга
- subscriptions: подписки на уведомления (Telegram)
- changes: журнал изменений в расписании
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
    
    Обеспечивает:
    - Хранение расписания по группам
    - Отслеживание времени последнего обновления
    - Обнаружение изменений в расписании
    - Управление подписками на уведомления
    """
    
    def __init__(self, db_path: str = "schedule.db"):
        self.db_path = db_path
        self.initialize()
    
    @contextmanager
    def get_connection(self):
        """
        Контекстный менеджер для подключения к БД.
        
        Автоматически коммитит изменения или откатывает при ошибке.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging для лучшей производительности
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
        """
        Инициализация базы данных.
        
        Создаёт все необходимые таблицы и индексы.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ========================================
            # Таблица групп
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    specialty TEXT DEFAULT '',
                    education_form TEXT DEFAULT 'Очная',
                    building TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            # ========================================
            # Таблица расписания
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    lesson_number INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    subject TEXT,
                    lesson_type TEXT DEFAULT 'practice',
                    teacher TEXT DEFAULT '',
                    room TEXT DEFAULT '',
                    building TEXT DEFAULT '',
                    is_changed INTEGER DEFAULT 0,
                    comment TEXT DEFAULT '',
                    source_url TEXT DEFAULT '',
                    updated_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # ========================================
            # Таблица времени последнего обновления
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS last_update (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_success TEXT,
                    last_attempt TEXT,
                    next_scheduled TEXT,
                    source TEXT DEFAULT '',
                    success INTEGER DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    lessons_count INTEGER DEFAULT 0,
                    groups_count INTEGER DEFAULT 0,
                    pdf_files_count INTEGER DEFAULT 0
                )
            ''')
            
            # ========================================
            # Таблица подписок на уведомления
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    notification_types TEXT DEFAULT '["changes", "cancellations"]',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # ========================================
            # Таблица журнала изменений
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    day_of_week TEXT,
                    lesson_number INTEGER,
                    change_type TEXT,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    subject TEXT,
                    comment TEXT DEFAULT '',
                    detected_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES groups(id)
                )
            ''')
            
            # ========================================
            # Таблица источников PDF
            # ========================================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pdf_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT,
                    specialty TEXT,
                    building TEXT,
                    education_form TEXT,
                    last_hash TEXT DEFAULT '',
                    last_checked TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # ========================================
            # Индексы для быстрого поиска
            # ========================================
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_schedules_group_day
                ON schedules(group_id, day_of_week)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_schedules_updated
                ON schedules(updated_at)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_subscriptions_group
                ON subscriptions(group_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_subscriptions_active
                ON subscriptions(is_active)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_changes_detected
                ON changes(detected_at)
            ''')
            
            # Инициализация записи last_update, если её нет
            cursor.execute('''
                INSERT OR IGNORE INTO last_update (id, last_success, last_attempt, next_scheduled)
                VALUES (1, NULL, NULL, NULL)
            ''')
            
            logger.info("База данных инициализирована успешно")
    
    # ========================================
    # Методы для работы с группами
    # ========================================
    
    def get_all_groups(self) -> List[Dict]:
        """Получение списка всех групп"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM groups 
                ORDER BY education_form, specialty, name
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        """Получение группы по названию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def upsert_group(self, group_data: Dict) -> str:
        """
        Создание или обновление группы.
        
        Returns:
            ID группы
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Генерируем ID из названия
            group_id = self._generate_group_id(group_data['name'])
            
            cursor.execute('''
                INSERT INTO groups (id, name, specialty, education_form, building, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    specialty = excluded.specialty,
                    education_form = excluded.education_form,
                    building = excluded.building,
                    updated_at = excluded.updated_at
            ''', (
                group_id,
                group_data['name'],
                group_data.get('specialty', ''),
                group_data.get('education_form', 'Очная'),
                group_data.get('building', ''),
                now, now
            ))
            
            return group_id
    
    # ========================================
    # Методы для работы с расписанием
    # ========================================
    
    def get_schedule(self, group_id: str) -> Optional[Dict]:
        """
        Получение расписания группы.
        
        Returns:
            Расписание, сгруппированное по дням недели.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM schedules
                WHERE group_id = ?
                ORDER BY 
                    CASE day_of_week
                        WHEN 'Понедельник' THEN 1
                        WHEN 'Вторник' THEN 2
                        WHEN 'Среда' THEN 3
                        WHEN 'Четверг' THEN 4
                        WHEN 'Пятница' THEN 5
                        WHEN 'Суббота' THEN 6
                    END,
                    lesson_number
            ''', (group_id,))
            
            rows = cursor.fetchall()
            if not rows:
                return None
            
            # Группировка по дням
            days = {}
            for row in rows:
                day = row['day_of_week']
                if day not in days:
                    days[day] = {
                        'dayOfWeek': day,
                        'lessons': []
                    }
                
                days[day]['lessons'].append({
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
                'days': list(days.values())
            }
    
    def update_schedule_from_lessons(self, lessons: List[Dict], source_url: str = "") -> int:
        """
        Обновление расписания из списка занятий.
        
        Автоматически определяет изменения и помечает их.
        
        Returns:
            Количество обработанных занятий
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            count = 0
            
            for lesson_data in lessons:
                group_name = lesson_data.get('group', '')
                if not group_name:
                    continue
                
                # Получаем или создаём группу
                group_id = self.upsert_group({
                    'name': group_name,
                    'specialty': lesson_data.get('specialty', ''),
                    'education_form': lesson_data.get('education_form', 'Очная'),
                    'building': lesson_data.get('building', ''),
                })
                
                # Формируем уникальный ID занятия
                lesson_id = f"{group_id}_{lesson_data['day']}_{lesson_data['number']}"
                
                # Проверяем существующую запись для обнаружения изменений
                cursor.execute(
                    'SELECT * FROM schedules WHERE id = ?',
                    (lesson_id,)
                )
                existing = cursor.fetchone()
                
                is_changed = 0
                if existing:
                    is_changed = self._detect_changes_and_log(
                        conn, existing, lesson_data, group_id
                    )
                
                # Вставляем или обновляем
                cursor.execute('''
                    INSERT OR REPLACE INTO schedules
                    (id, group_id, day_of_week, lesson_number, start_time, end_time,
                     subject, lesson_type, teacher, room, building, is_changed,
                     comment, source_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    lesson_id,
                    group_id,
                    lesson_data.get('day', ''),
                    lesson_data.get('number', 0),
                    lesson_data.get('time', ''),
                    lesson_data.get('end_time', ''),
                    lesson_data.get('subject', ''),
                    lesson_data.get('type', 'practice'),
                    lesson_data.get('teacher', ''),
                    lesson_data.get('room', ''),
                    lesson_data.get('building', ''),
                    is_changed,
                    lesson_data.get('comment', ''),
                    source_url,
                    now
                ))
                count += 1
            
            return count
    
    def _detect_changes_and_log(
        self,
        conn: sqlite3.Connection,
        existing: sqlite3.Row,
        new_data: Dict,
        group_id: str
    ) -> int:
        """
        Обнаружение изменений в занятии и логирование.
        
        Сравнивает старое и новое значение, записывает изменения в журнал.
        
        Returns:
            1 если есть изменения, 0 если нет
        """
        changes_detected = 0
        now = datetime.now().isoformat()
        
        # Поля для сравнения
        fields_to_check = [
            ('subject', 'subject'),
            ('teacher', 'teacher'),
            ('room', 'room'),
            ('lesson_type', 'type'),
            ('start_time', 'time'),
        ]
        
        for db_field, data_field in fields_to_check:
            old_value = existing[db_field] or ''
            new_value = new_data.get(data_field, '')
            
            if old_value != new_value and new_value:
                changes_detected = 1
                
                # Логируем изменение
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO changes
                    (group_id, day_of_week, lesson_number, change_type,
                     field_name, old_value, new_value, subject, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    group_id,
                    existing['day_of_week'],
                    existing['lesson_number'],
                    'modified',
                    db_field,
                    old_value,
                    new_value,
                    new_data.get('subject', ''),
                    now
                ))
                
                logger.info(
                    f"Изменение: {group_id} {existing['day_of_week']} "
                    f"#{existing['lesson_number']} — {db_field}: "
                    f"'{old_value}' → '{new_value}'"
                )
        
        return changes_detected
    
    # ========================================
    # Методы для работы с last_update
    # ========================================
    
    def get_last_update(self) -> Dict:
        """
        Получение информации о последнем обновлении.
        
        Returns:
            Словарь с информацией о последнем успешном обновлении.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM last_update WHERE id = 1')
            row = cursor.fetchone()
            
            if row:
                data = dict(row)
                return {
                    'lastUpdate': data.get('last_success'),
                    'lastAttempt': data.get('last_attempt'),
                    'nextScheduled': data.get('next_scheduled'),
                    'source': data.get('source', ''),
                    'success': bool(data.get('success', 0)),
                    'errorMessage': data.get('error_message', ''),
                    'lessonsCount': data.get('lessons_count', 0),
                    'groupsCount': data.get('groups_count', 0),
                    'pdfFilesCount': data.get('pdf_files_count', 0),
                }
            
            return {
                'lastUpdate': None,
                'lastAttempt': None,
                'nextScheduled': None,
                'source': '',
                'success': False,
                'errorMessage': 'Данные ещё не обновлялись',
                'lessonsCount': 0,
                'groupsCount': 0,
                'pdfFilesCount': 0,
            }
    
    def set_last_update(
        self,
        success: bool,
        source: str = "",
        error_message: str = "",
        lessons_count: int = 0,
        groups_count: int = 0,
        pdf_files_count: int = 0
    ):
        """
        Установка информации о последнем обновлении.
        
        Args:
            success: Успешно ли обновление
            source: Источник данных
            error_message: Сообщение об ошибке (если есть)
            lessons_count: Количество обработанных занятий
            groups_count: Количество групп
            pdf_files_count: Количество обработанных PDF файлов
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Следующее обновление через 24 часа
            next_update = (datetime.now() + timedelta(hours=24)).isoformat()
            
            cursor.execute('''
                UPDATE last_update SET
                    last_success = CASE WHEN ? THEN ? ELSE last_success END,
                    last_attempt = ?,
                    next_scheduled = ?,
                    source = ?,
                    success = ?,
                    error_message = ?,
                    lessons_count = ?,
                    groups_count = ?,
                    pdf_files_count = ?
                WHERE id = 1
            ''', (
                1 if success else 0, now,
                now,
                next_update,
                source,
                1 if success else 0,
                error_message,
                lessons_count,
                groups_count,
                pdf_files_count
            ))
            
            logger.info(
                f"Обновление last_update: success={success}, "
                f"lessons={lessons_count}, groups={groups_count}"
            )
    
    def needs_update(self) -> bool:
        """
        Проверка, нужно ли обновление данных.
        
        Возвращает True если:
        - Данных нет вообще
        - Последнее обновление было более 24 часов назад
        - Последнее обновление было неудачным
        """
        update_info = self.get_last_update()
        
        # Если данных никогда не было
        if not update_info['lastUpdate']:
            return True
        
        # Если последнее обновление было неудачным
        if not update_info['success']:
            return True
        
        # Проверяем, прошло ли 24 часа
        try:
            last_update = datetime.fromisoformat(update_info['lastUpdate'])
            hours_passed = (datetime.now() - last_update).total_seconds() / 3600
            return hours_passed >= 24
        except (ValueError, TypeError):
            return True
    
    # ========================================
    # Методы для работы с подписками
    # ========================================
    
    def add_subscription(self, chat_id: str, group_id: str, notification_types: List[str] = None) -> bool:
        """Добавление подписки на уведомления"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            types_json = json.dumps(notification_types or ['changes', 'cancellations'])
            
            try:
                cursor.execute('''
                    INSERT INTO subscriptions (chat_id, group_id, notification_types, is_active, created_at)
                    VALUES (?, ?, ?, 1, ?)
                ''', (chat_id, group_id, types_json, now))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def remove_subscription(self, chat_id: str, group_id: str = None):
        """Удаление подписки"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if group_id:
                cursor.execute(
                    'DELETE FROM subscriptions WHERE chat_id = ? AND group_id = ?',
                    (chat_id, group_id)
                )
            else:
                cursor.execute(
                    'DELETE FROM subscriptions WHERE chat_id = ?',
                    (chat_id,)
                )
    
    def get_subscriptions_for_group(self, group_id: str) -> List[Dict]:
        """Получение подписок для группы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM subscriptions
                WHERE group_id = ? AND is_active = 1
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========================================
    # Методы для работы с журналом изменений
    # ========================================
    
    def get_recent_changes(self, hours: int = 24) -> List[Dict]:
        """Получение недавних изменений"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            cursor.execute('''
                SELECT c.*, g.name as group_name
                FROM changes c
                LEFT JOIN groups g ON c.group_id = g.id
                WHERE c.detected_at > ?
                ORDER BY c.detected_at DESC
            ''', (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ========================================
    # Служебные методы
    # ========================================
    
    def cleanup_old_data(self, days: int = 30):
        """Очистка устаревших данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Удаляем старые записи журнала изменений
            cursor.execute('DELETE FROM changes WHERE detected_at < ?', (cutoff,))
            changes_deleted = cursor.rowcount
            
            logger.info(f"Очистка: удалено {changes_deleted} записей изменений")
    
    def get_stats(self) -> Dict:
        """Получение статистики базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM groups')
            groups_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM schedules')
            schedules_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT group_id) FROM schedules')
            active_groups = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM subscriptions WHERE is_active = 1')
            subscriptions_count = cursor.fetchone()[0]
            
            return {
                'totalGroups': groups_count,
                'totalSchedules': schedules_count,
                'activeGroups': active_groups,
                'activeSubscriptions': subscriptions_count,
            }
    
    def _generate_group_id(self, name: str) -> str:
        """Генерация ID группы из названия"""
        # Транслитерация и очистка
        import hashlib
        clean_name = name.strip().lower().replace(' ', '_')
        hash_part = hashlib.md5(clean_name.encode()).hexdigest()[:6]
        return f"grp_{clean_name}_{hash_part}"
