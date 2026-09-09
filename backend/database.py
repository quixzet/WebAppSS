"""
Модуль работы с базой данных SQLite для приложения расписания.

Полностью переработан для устранения проблемы "database is locked":
- Единое соединение с WAL-режимом
- threading.Lock для синхронизации записи
- Retry механизм с экспоненциальной задержкой
- Bulk операции через executemany
- Единая транзакция для массовых вставок
- BEGIN IMMEDIATE для захвата эксклюзивной блокировки

Основные изменения:
1. Все операции записи проходят через threading.Lock
2. bulk_update_schedule выполняет всё в одной транзакции
3. Retry декоратор автоматически повторяет при блокировке
4. WAL-режим позволяет одновременное чтение/запись
5. Увеличен таймаут ожидания блокировки до 30 секунд
"""

import sqlite3
import json
import logging
import threading
import time
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from functools import wraps

from db_config import (
    DATABASE_PATH,
    DATABASE_TIMEOUT,
    WAL_MODE,
    SYNC_MODE,
    CACHE_SIZE,
    MMAP_SIZE,
    MAX_RETRY_ATTEMPTS,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
    BATCH_SIZE,
    LOG_QUERY_TIMING,
    SLOW_QUERY_THRESHOLD,
    CREATE_INDEXES,
    INDEXES,
)

logger = logging.getLogger(__name__)


# ========================================
# Декоратор retry_on_lock
# ========================================

def retry_on_lock(max_attempts: int = MAX_RETRY_ATTEMPTS, base_delay: float = RETRY_BASE_DELAY):
    """
    Декоратор для повторных попыток при ошибке блокировки БД.
    
    Использует экспоненциальную задержку: base_delay * (2 ^ attempt)
    Повторяет до max_attempts раз.
    
    Args:
        max_attempts: Максимальное количество попыток
        base_delay: Базовая задержка в секундах
    
    Example:
        @retry_on_lock(max_attempts=5, base_delay=0.5)
        def bulk_update_schedule(self, lessons):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    # Проверяем, что это именно ошибка блокировки
                    if "locked" in error_msg or "busy" in error_msg:
                        last_exception = e
                        
                        if attempt < max_attempts - 1:
                            # Экспоненциальная задержка с максимумом
                            delay = min(base_delay * (2 ** attempt), RETRY_MAX_DELAY)
                            logger.warning(
                                f"Блокировка БД в {func.__name__} "
                                f"(попытка {attempt + 1}/{max_attempts}). "
                                f"Ожидание {delay:.1f}с..."
                            )
                            time.sleep(delay)
                        else:
                            logger.error(
                                f"Превышено максимальное количество попыток "
                                f"({max_attempts}) в {func.__name__}"
                            )
                    else:
                        # Другая OperationalError — не повторяем
                        raise
                
                except Exception as e:
                    # Другие исключения — не повторяем
                    raise
            
            # Если все попытки исчерпаны
            raise last_exception
        
        return wrapper
    return decorator


# ========================================
# Класс Database
# ========================================

class Database:
    """
    Потокобезопасный менеджер базы данных SQLite.
    
    Ключевые особенности:
    - Единое соединение с WAL-режимом
    - threading.Lock для синхронизации операций записи
    - Retry механизм при блокировке
    - Bulk операции для массовых вставок
    - Единая транзакция для атомарности
    
    Использование:
        db = Database()
        
        # Массовое обновление (рекомендуется)
        stats = db.bulk_update_schedule(all_lessons, sources)
        
        # Одиночные операции (для мелких задач)
        groups = db.get_all_groups()
        schedule = db.get_schedule(group_id)
    """
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """
        Инициализация базы данных.
        
        Создаёт соединение, настраивает WAL-режим, создаёт таблицы и индексы.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._lock = threading.Lock()  # Lock для синхронизации записи
        self._init_db()
        
        logger.info(f"✅ База данных инициализирована: {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Получить соединение с БД с оптимальными настройками.
        
        Настройки:
        - timeout: 30 секунд ожидания блокировки
        - check_same_thread: False для многопоточности
        - WAL-режим для одновременного чтения/записи
        - Увеличенный кэш и mmap_size
        
        Returns:
            sqlite3.Connection с настроенными параметрами
        """
        conn = sqlite3.connect(
            self.db_path,
            timeout=DATABASE_TIMEOUT,
            check_same_thread=False,  # Разрешаем использование из разных потоков
            isolation_level=None  # Ручное управление транзакциями
        )
        
        # Настройка row_factory для доступа по именам колонок
        conn.row_factory = sqlite3.Row
        
        # Прагмы для оптимизации
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA synchronous={SYNC_MODE}")
        conn.execute(f"PRAGMA cache_size={CACHE_SIZE}")
        conn.execute(f"PRAGMA mmap_size={MMAP_SIZE}")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        
        return conn
    
    def _init_db(self):
        """
        Инициализация структуры базы данных.
        
        Создаёт все необходимые таблицы и индексы.
        Настраивает WAL-режим и другие параметры.
        """
        start_time = time.time()
        
        with self._lock:
            conn = self._get_connection()
            try:
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
                
                # Инициализация записи last_update
                cursor.execute('''
                    INSERT OR IGNORE INTO last_update (id, last_success, last_attempt, next_scheduled)
                    VALUES (1, NULL, NULL, NULL)
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
                # Создание индексов
                # ========================================
                if CREATE_INDEXES:
                    for index in INDEXES:
                        columns = ", ".join(index["columns"])
                        cursor.execute(f'''
                            CREATE INDEX IF NOT EXISTS {index["name"]}
                            ON {index["table"]}({columns})
                        ''')
                
                conn.commit()
                
                elapsed = time.time() - start_time
                if LOG_QUERY_TIMING and elapsed > SLOW_QUERY_THRESHOLD:
                    logger.warning(f"⚠️ Медленная инициализация БД: {elapsed:.2f}с")
                else:
                    logger.debug(f"Инициализация БД завершена за {elapsed:.2f}с")
            
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
                raise
            finally:
                conn.close()
    
    # ========================================
    # Context manager для транзакций
    # ========================================
    
    @contextmanager
    def transaction(self):
        """
        Контекстный менеджер для атомарных транзакций.
        
        Использует threading.Lock для синхронизации.
        Начинает транзакцию с BEGIN IMMEDIATE для захвата эксклюзивной блокировки.
        
        Example:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
                conn.execute("UPDATE ...")
                # Все изменения применятся атомарно
        """
        with self._lock:
            conn = self._get_connection()
            try:
                # BEGIN IMMEDIATE захватывает эксклюзивную блокировку сразу
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.execute("COMMIT")
            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"Ошибка транзакции, выполнен откат: {e}")
                raise
            finally:
                conn.close()
    
    # ========================================
    # Методы для работы с группами
    # ========================================
    
    def get_all_groups(self) -> List[Dict]:
        """
        Получить список всех групп.
        
        Returns:
            Список словарей с информацией о группах
        """
        start_time = time.time()
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM groups 
                ORDER BY education_form, specialty, name
            ''')
            result = [dict(row) for row in cursor.fetchall()]
            
            elapsed = time.time() - start_time
            if LOG_QUERY_TIMING and elapsed > SLOW_QUERY_THRESHOLD:
                logger.warning(f"⚠️ Медленный запрос get_all_groups: {elapsed:.2f}с")
            
            return result
        finally:
            conn.close()
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        """
        Получить группу по названию.
        
        Args:
            name: Название группы
        
        Returns:
            Словарь с информацией о группе или None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    @retry_on_lock()
    def upsert_group(self, group_data: Dict) -> str:
        """
        Создать или обновить группу.
        
        Использует INSERT ... ON CONFLICT DO UPDATE для атомарности.
        
        Args:
            group_data: Словарь с данными группы
        
        Returns:
            ID группы
        """
        group_id = self._generate_group_id(group_data['name'])
        now = datetime.now().isoformat()
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO groups (id, name, specialty, education_form, building, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    specialty = excluded.specialty,
                    education_form = excluded.education_form,
                    building = excluded.building,
                    updated_at = excluded.updated_at
                RETURNING id
            ''', (
                group_id,
                group_data['name'],
                group_data.get('specialty', ''),
                group_data.get('education_form', 'Очная'),
                group_data.get('building', ''),
                now, now
            ))
            
            result = cursor.fetchone()
            return result[0] if result else group_id
    
    # ========================================
    # Методы для работы с расписанием
    # ========================================
    
    def get_schedule(self, group_id: str) -> Optional[Dict]:
        """
        Получить расписание группы.
        
        Args:
            group_id: ID группы
        
        Returns:
            Словарь с расписанием, сгруппированным по дням недели
        """
        start_time = time.time()
        
        conn = self._get_connection()
        try:
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
            
            elapsed = time.time() - start_time
            if LOG_QUERY_TIMING and elapsed > SLOW_QUERY_THRESHOLD:
                logger.warning(f"⚠️ Медленный запрос get_schedule: {elapsed:.2f}с")
            
            return {
                'days': list(days.values())
            }
        finally:
            conn.close()
    
    @retry_on_lock()
    def bulk_update_schedule(
        self,
        all_lessons: List[Dict],
        source_url: str = ""
    ) -> Dict:
        """
        Массовое обновление расписания из списка занятий.
        
        КЛЮЧЕВОЙ МЕТОД для устранения "database is locked":
        1. Собирает все уникальные группы
        2. Вставляет группы через executemany
        3. Получает ID всех групп
        4. Вставляет занятия через executemany
        5. Всё в ОДНОЙ транзакции с BEGIN IMMEDIATE
        
        Args:
            all_lessons: Список всех занятий из всех PDF
            source_url: URL источника данных
        
        Returns:
            Словарь со статистикой:
            {
                'total_lessons': int,
                'total_groups': int,
                'updated_groups': int,
                'elapsed_seconds': float
            }
        """
        start_time = time.time()
        
        logger.info(f"🚀 Начало массового обновления: {len(all_lessons)} занятий")
        
        if not all_lessons:
            logger.warning("Список занятий пуст, обновление пропущено")
            return {
                'total_lessons': 0,
                'total_groups': 0,
                'updated_groups': 0,
                'elapsed_seconds': 0.0
            }
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # ========================================
            # Шаг 1: Собрать все уникальные группы
            # ========================================
            unique_groups = {}
            for lesson in all_lessons:
                group_name = lesson.get('group', '').strip()
                if not group_name:
                    continue
                
                if group_name not in unique_groups:
                    unique_groups[group_name] = {
                        'name': group_name,
                        'specialty': lesson.get('specialty', ''),
                        'education_form': lesson.get('education_form', 'Очная'),
                        'building': lesson.get('building', ''),
                    }
            
            logger.info(f"📊 Найдено {len(unique_groups)} уникальных групп")
            
            # ========================================
            # Шаг 2: Массовая вставка групп через executemany
            # ========================================
            groups_data = [
                (
                    self._generate_group_id(g['name']),
                    g['name'],
                    g['specialty'],
                    g['education_form'],
                    g['building'],
                    now,
                    now
                )
                for g in unique_groups.values()
            ]
            
            cursor.executemany('''
                INSERT INTO groups (id, name, specialty, education_form, building, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    specialty = excluded.specialty,
                    education_form = excluded.education_form,
                    building = excluded.building,
                    updated_at = excluded.updated_at
            ''', groups_data)
            
            logger.debug(f"✅ Вставлено/обновлено {len(groups_data)} групп")
            
            # ========================================
            # Шаг 3: Получить ID всех групп
            # ========================================
            cursor.execute('SELECT id, name FROM groups')
            group_ids = {row['name']: row['id'] for row in cursor.fetchall()}
            
            # ========================================
            # Шаг 4: Подготовить данные для занятий
            # ========================================
            schedules_data = []
            changes_data = []
            
            for lesson in all_lessons:
                group_name = lesson.get('group', '').strip()
                if not group_name or group_name not in group_ids:
                    continue
                
                group_id = group_ids[group_name]
                day = lesson.get('day', '')
                number = lesson.get('number', 0)
                
                # Уникальный ID занятия
                lesson_id = f"{group_id}_{day}_{number}"
                
                # Проверка существующей записи для обнаружения изменений
                cursor.execute(
                    'SELECT subject, teacher, room, lesson_type, start_time FROM schedules WHERE id = ?',
                    (lesson_id,)
                )
                existing = cursor.fetchone()
                
                is_changed = 0
                if existing:
                    # Обнаружение изменений
                    changes = self._detect_changes(
                        existing, lesson, group_id, day, number, now
                    )
                    if changes:
                        is_changed = 1
                        changes_data.extend(changes)
                
                # Данные для вставки
                schedules_data.append((
                    lesson_id,
                    group_id,
                    day,
                    number,
                    lesson.get('time', ''),
                    lesson.get('end_time', ''),
                    lesson.get('subject', ''),
                    lesson.get('type', 'practice'),
                    lesson.get('teacher', ''),
                    lesson.get('room', ''),
                    lesson.get('building', ''),
                    is_changed,
                    lesson.get('comment', ''),
                    source_url,
                    now
                ))
            
            # ========================================
            # Шаг 5: Массовая вставка занятий через executemany
            # ========================================
            if schedules_data:
                # Разбиваем на батчи если данных очень много
                for i in range(0, len(schedules_data), BATCH_SIZE):
                    batch = schedules_data[i:i + BATCH_SIZE]
                    cursor.executemany('''
                        INSERT OR REPLACE INTO schedules
                        (id, group_id, day_of_week, lesson_number, start_time, end_time,
                         subject, lesson_type, teacher, room, building, is_changed,
                         comment, source_url, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch)
                    
                    logger.debug(f"✅ Вставлено {len(batch)} занятий (батч {i // BATCH_SIZE + 1})")
            
            # ========================================
            # Шаг 6: Вставка изменений в журнал
            # ========================================
            if changes_data:
                cursor.executemany('''
                    INSERT INTO changes
                    (group_id, day_of_week, lesson_number, change_type,
                     field_name, old_value, new_value, subject, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', changes_data)
                
                logger.info(f"📝 Записано {len(changes_data)} изменений в журнал")
            
            elapsed = time.time() - start_time
            
            result = {
                'total_lessons': len(schedules_data),
                'total_groups': len(unique_groups),
                'updated_groups': len(groups_data),
                'changes_detected': len(changes_data),
                'elapsed_seconds': elapsed
            }
            
            logger.info(
                f"✅ Массовое обновление завершено за {elapsed:.2f}с: "
                f"{result['total_lessons']} занятий, "
                f"{result['total_groups']} групп, "
                f"{result['changes_detected']} изменений"
            )
            
            return result
    
    def _detect_changes(
        self,
        existing: sqlite3.Row,
        new_lesson: Dict,
        group_id: str,
        day: str,
        number: int,
        timestamp: str
    ) -> List[Tuple]:
        """
        Обнаружение изменений в занятии.
        
        Сравнивает старое и новое значение, формирует записи для журнала.
        
        Returns:
            Список кортежей для вставки в таблицу changes
        """
        changes = []
        
        fields_to_check = [
            ('subject', 'subject'),
            ('teacher', 'teacher'),
            ('room', 'room'),
            ('lesson_type', 'type'),
            ('start_time', 'time'),
        ]
        
        for db_field, data_field in fields_to_check:
            old_value = existing[db_field] or ''
            new_value = new_lesson.get(data_field, '')
            
            if old_value != new_value and new_value:
                changes.append((
                    group_id,
                    day,
                    number,
                    'modified',
                    db_field,
                    old_value,
                    new_value,
                    new_lesson.get('subject', ''),
                    timestamp
                ))
                
                logger.debug(
                    f"Изменение: {group_id} {day} #{number} — "
                    f"{db_field}: '{old_value}' → '{new_value}'"
                )
        
        return changes
    
    # ========================================
    # Методы для работы с last_update
    # ========================================
    
    def get_last_update(self) -> Dict:
        """
        Получить информацию о последнем обновлении.
        
        Returns:
            Словарь с информацией о последнем обновлении
        """
        conn = self._get_connection()
        try:
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
        finally:
            conn.close()
    
    @retry_on_lock()
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
        Установить информацию о последнем обновлении.
        
        Args:
            success: Успешно ли обновление
            source: Источник данных
            error_message: Сообщение об ошибке
            lessons_count: Количество обработанных занятий
            groups_count: Количество групп
            pdf_files_count: Количество обработанных PDF файлов
        """
        now = datetime.now().isoformat()
        next_update = (datetime.now() + timedelta(hours=24)).isoformat()
        
        with self.transaction() as conn:
            cursor = conn.cursor()
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
            f"📊 Обновлено last_update: success={success}, "
            f"lessons={lessons_count}, groups={groups_count}"
        )
    
    def needs_update(self) -> bool:
        """
        Проверка, нужно ли обновление данных.
        
        Returns:
            True если данных нет или они старше 24 часов
        """
        update_info = self.get_last_update()
        
        if not update_info['lastUpdate']:
            return True
        
        if not update_info['success']:
            return True
        
        try:
            last_update = datetime.fromisoformat(update_info['lastUpdate'])
            hours_passed = (datetime.now() - last_update).total_seconds() / 3600
            return hours_passed >= 24
        except (ValueError, TypeError):
            return True
    
    # ========================================
    # Служебные методы
    # ========================================
    
    def cleanup_old_data(self, days: int = 30):
        """Очистка устаревших данных"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM changes WHERE detected_at < ?', (cutoff,))
            deleted = cursor.rowcount
        
        logger.info(f"🧹 Очистка: удалено {deleted} записей изменений")
    
    def get_stats(self) -> Dict:
        """Получение статистики базы данных"""
        conn = self._get_connection()
        try:
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
        finally:
            conn.close()
    
    def _generate_group_id(self, name: str) -> str:
        """Генерация ID группы из названия"""
        clean_name = name.strip().lower().replace(' ', '_')
        hash_part = hashlib.md5(clean_name.encode()).hexdigest()[:6]
        return f"grp_{clean_name}_{hash_part}"
