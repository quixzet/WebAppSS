"""
Миграционный скрипт для перевода существующей базы данных на WAL-режим.

Запускается один раз при первом запуске обновлённой версии приложения.
Выполняет:
1. Проверку текущего режима журналирования
2. Переключение на WAL-режим
3. Настройку параметров производительности
4. Создание недостающих индексов
5. Валидацию структуры таблиц

Использование:
    python migrate_db.py

Или автоматически при запуске main.py (через Database.__init__)
"""

import sqlite3
import logging
import sys
from pathlib import Path

from db_config import (
    DATABASE_PATH,
    DATABASE_TIMEOUT,
    WAL_MODE,
    SYNC_MODE,
    CACHE_SIZE,
    MMAP_SIZE,
    INDEXES,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_database_exists(db_path: str) -> bool:
    """Проверка существования файла базы данных"""
    return Path(db_path).exists()


def get_current_journal_mode(conn: sqlite3.Connection) -> str:
    """Получение текущего режима журналирования"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    return cursor.fetchone()[0]


def migrate_to_wal(db_path: str = DATABASE_PATH):
    """
    Основная функция миграции.
    
    Выполняет все необходимые операции для перевода БД на WAL-режим
    и настройки оптимальных параметров производительности.
    """
    logger.info("=" * 60)
    logger.info("🔧 Начало миграции базы данных")
    logger.info("=" * 60)
    
    # Проверка существования БД
    if not check_database_exists(db_path):
        logger.info(f"📁 База данных не найдена: {db_path}")
        logger.info("💡 Она будет создана при первом запуске приложения")
        return
    
    logger.info(f"📁 Найден файл БД: {db_path}")
    
    # Подключение к БД
    conn = sqlite3.connect(db_path, timeout=DATABASE_TIMEOUT)
    
    try:
        cursor = conn.cursor()
        
        # ========================================
        # Шаг 1: Проверка текущего режима
        # ========================================
        current_mode = get_current_journal_mode(conn)
        logger.info(f"📊 Текущий режим журналирования: {current_mode}")
        
        # ========================================
        # Шаг 2: Переключение на WAL-режим
        # ========================================
        if current_mode.lower() != 'wal' and WAL_MODE:
            logger.info("🔄 Переключение на WAL-режим...")
            cursor.execute("PRAGMA journal_mode=WAL")
            new_mode = cursor.fetchone()[0]
            logger.info(f"✅ Режим журналирования: {new_mode}")
        else:
            logger.info("✅ WAL-режим уже активен")
        
        # ========================================
        # Шаг 3: Настройка параметров производительности
        # ========================================
        logger.info("⚙️ Настройка параметров производительности...")
        
        # Режим синхронизации
        cursor.execute(f"PRAGMA synchronous={SYNC_MODE}")
        cursor.execute("PRAGMA synchronous")
        sync_value = cursor.fetchone()[0]
        logger.info(f"  ✅ synchronous = {sync_value} ({SYNC_MODE})")
        
        # Размер кэша
        cursor.execute(f"PRAGMA cache_size={CACHE_SIZE}")
        cursor.execute("PRAGMA cache_size")
        cache_value = cursor.fetchone()[0]
        cache_mb = abs(cache_value) / 1024  # В MB
        logger.info(f"  ✅ cache_size = {cache_mb:.0f} MB")
        
        # Memory-mapped I/O
        cursor.execute(f"PRAGMA mmap_size={MMAP_SIZE}")
        cursor.execute("PRAGMA mmap_size")
        mmap_value = cursor.fetchone()[0]
        mmap_mb = mmap_value / (1024 * 1024) if mmap_value > 0 else 0
        logger.info(f"  ✅ mmap_size = {mmap_mb:.0f} MB")
        
        # Temp store в памяти
        cursor.execute("PRAGMA temp_store=MEMORY")
        logger.info("  ✅ temp_store = MEMORY")
        
        # Foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")
        logger.info("  ✅ foreign_keys = ON")
        
        conn.commit()
        
        # ========================================
        # Шаг 4: Создание индексов
        # ========================================
        logger.info("📇 Проверка и создание индексов...")
        
        for index in INDEXES:
            index_name = index["name"]
            table_name = index["table"]
            columns = ", ".join(index["columns"])
            
            # Проверка существования индекса
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                (index_name,)
            )
            
            if cursor.fetchone():
                logger.debug(f"  ⏭️ Индекс {index_name} уже существует")
            else:
                cursor.execute(f'''
                    CREATE INDEX {index_name}
                    ON {table_name}({columns})
                ''')
                logger.info(f"  ✅ Создан индекс: {index_name}")
        
        conn.commit()
        
        # ========================================
        # Шаг 5: Валидация структуры таблиц
        # ========================================
        logger.info("🔍 Валидация структуры таблиц...")
        
        required_tables = [
            'groups', 'schedules', 'last_update',
            'subscriptions', 'changes'
        ]
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table in required_tables:
            if table in existing_tables:
                logger.debug(f"  ✅ Таблица {table} существует")
            else:
                logger.warning(f"  ⚠️ Таблица {table} отсутствует!")
        
        # ========================================
        # Шаг 6: Статистика
        # ========================================
        logger.info("📊 Статистика базы данных:")
        
        for table in required_tables:
            if table in existing_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                logger.info(f"  {table}: {count} записей")
        
        # Размер файла БД
        db_size = Path(db_path).stat().st_size
        db_size_mb = db_size / (1024 * 1024)
        logger.info(f"  Размер файла: {db_size_mb:.2f} MB")
        
        # Проверка WAL файла
        wal_path = f"{db_path}-wal"
        if Path(wal_path).exists():
            wal_size = Path(wal_path).stat().st_size
            wal_size_mb = wal_size / (1024 * 1024)
            logger.info(f"  WAL файл: {wal_size_mb:.2f} MB")
        
        logger.info("=" * 60)
        logger.info("✅ Миграция завершена успешно!")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"❌ Ошибка миграции: {e}", exc_info=True)
        conn.rollback()
        raise
    
    finally:
        conn.close()


def vacuum_database(db_path: str = DATABASE_PATH):
    """
    Выполнить VACUUM для оптимизации размера БД.
    
    Рекомендуется запускать периодически (раз в неделю).
    """
    if not check_database_exists(db_path):
        logger.info("База данных не найдена, VACUUM пропущен")
        return
    
    logger.info("🗜 Начало VACUUM...")
    
    conn = sqlite3.connect(db_path, timeout=DATABASE_TIMEOUT)
    try:
        old_size = Path(db_path).stat().st_size
        conn.execute("VACUUM")
        new_size = Path(db_path).stat().st_size
        
        saved = old_size - new_size
        saved_mb = saved / (1024 * 1024)
        
        logger.info(
            f"✅ VACUUM завершён. "
            f"Освобождено: {saved_mb:.2f} MB "
            f"({old_size / (1024*1024):.2f} → {new_size / (1024*1024):.2f} MB)"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка VACUUM: {e}")
    finally:
        conn.close()


def check_integrity(db_path: str = DATABASE_PATH) -> bool:
    """
    Проверка целостности базы данных.
    
    Returns:
        True если БД в хорошем состоянии
    """
    if not check_database_exists(db_path):
        return True
    
    conn = sqlite3.connect(db_path, timeout=DATABASE_TIMEOUT)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        
        if result == 'ok':
            logger.info("✅ Проверка целостности: OK")
            return True
        else:
            logger.error(f"❌ Проверка целостности: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка проверки целостности: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Миграция базы данных расписания")
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Выполнить VACUUM для оптимизации размера"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Проверить целостность базы данных"
    )
    parser.add_argument(
        "--db-path",
        default=DATABASE_PATH,
        help=f"Путь к файлу БД (по умолчанию: {DATABASE_PATH})"
    )
    
    args = parser.parse_args()
    
    if args.vacuum:
        vacuum_database(args.db_path)
    elif args.check:
        check_integrity(args.db_path)
    else:
        migrate_to_wal(args.db_path)
