"""
Парсер PDF файлов расписания с сайта СИЭУиП (https://sielom.ru/schedule)

Обрабатывает PDF файлы, загруженные на сайт института.
Извлекает структурированные данные о занятиях:
- Группа
- День недели
- Время
- Предмет
- Тип занятия (лекция/практика/лабораторная)
- Преподаватель
- Аудитория

Использует pdfplumber для извлечения текста и таблиц из PDF.
"""

import aiohttp
import asyncio
import pdfplumber
import re
import logging
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from .html_parser import PDFSource, DEFAULT_USER_AGENT, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


@dataclass
class ScheduleLesson:
    """Модель одного занятия"""
    group: str                # Название группы (например, "ИС-201")
    day: str                  # День недели (Понедельник, Вторник, ...)
    number: int               # Номер пары (1-6)
    time: str                 # Время начала (например, "08:30")
    end_time: str = ""        # Время окончания
    subject: str = ""         # Название предмета
    type: str = "practice"    # Тип: lecture, practice, lab, exam, consultation
    teacher: str = ""         # Преподаватель
    room: str = ""            # Аудитория
    building: str = ""        # Корпус
    comment: str = ""         # Комментарий
    updated_at: str = ""      # Время обновления


@dataclass
class PDFParseResult:
    """Результат парсинга одного PDF файла"""
    source: PDFSource
    success: bool
    lessons: List[ScheduleLesson] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    error: str = ""
    timestamp: str = ""


# Стандартные временные слоты пар (для российских вузов)
LESSON_TIMES = {
    1: ("08:30", "10:00"),
    2: ("10:15", "11:45"),
    3: ("12:30", "14:00"),
    4: ("14:15", "15:45"),
    5: ("16:00", "17:30"),
    6: ("17:45", "19:15"),
}

# Дни недели
DAYS_OF_WEEK = [
    "Понедельник", "Вторник", "Среда",
    "Четверг", "Пятница", "Суббота"
]

# Паттерны для определения дней недели в тексте
DAY_PATTERNS = {
    "Понедельник": r"(?:понедельник|пн|пнд)\b",
    "Вторник": r"(?:вторник|вт|втр)\b",
    "Среда": r"(?:среда|ср|срд)\b",
    "Четверг": r"(?:четверг|чт|чтв)\b",
    "Пятница": r"(?:пятница|пт|птн)\b",
    "Суббота": r"(?:суббота|сб|суб)\b",
}


class PDFScheduleParser:
    """
    Парсер PDF файлов с расписанием.
    
    Обрабатывает PDF файлы, загруженные с сайта СИЭУиП.
    Поддерживает различные форматы расписания:
    - Табличный формат (основной)
    - Текстовый формат (резервный)
    """
    
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = MAX_RETRIES,
        retry_delay: int = RETRY_DELAY,
    ):
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.user_agent}
            )
        return self._session
    
    async def close(self):
        """Закрыть HTTP сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def parse_source(self, source: PDFSource) -> PDFParseResult:
        """
        Парсинг одного PDF источника.
        
        Загружает PDF файл и извлекает из него расписание.
        """
        logger.info(f"Парсинг PDF: {source.title} ({source.url})")
        
        # Загрузка PDF
        pdf_bytes = await self._fetch_pdf(source.url)
        
        if pdf_bytes is None:
            return PDFParseResult(
                source=source,
                success=False,
                error=f"Не удалось загрузить PDF: {source.url}",
                timestamp=datetime.now().isoformat()
            )
        
        # Парсинг PDF
        try:
            lessons, groups = self._extract_from_pdf(pdf_bytes, source)
            
            if not lessons:
                return PDFParseResult(
                    source=source,
                    success=False,
                    error="Не удалось извлечь занятия из PDF. "
                          "Возможно, файл имеет нестандартный формат.",
                    timestamp=datetime.now().isoformat()
                )
            
            logger.info(
                f"Извлечено {len(lessons)} занятий, "
                f"{len(groups)} групп из {source.title}"
            )
            
            return PDFParseResult(
                source=source,
                success=True,
                lessons=lessons,
                groups=groups,
                timestamp=datetime.now().isoformat()
            )
        
        except Exception as e:
            logger.error(f"Ошибка парсинга PDF {source.title}: {e}", exc_info=True)
            return PDFParseResult(
                source=source,
                success=False,
                error=f"Ошибка парсинга: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    async def parse_multiple(self, sources: List[PDFSource]) -> List[PDFParseResult]:
        """
        Парсинг нескольких PDF источников.
        
        Обрабатывает файлы параллельно с ограничением на количество
        одновременных загрузок.
        """
        semaphore = asyncio.Semaphore(3)  # Максимум 3 параллельных загрузки
        
        async def parse_with_limit(source: PDFSource) -> PDFParseResult:
            async with semaphore:
                return await self.parse_source(source)
        
        tasks = [parse_with_limit(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обработка исключений
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Ошибка при парсинге {sources[i].title}: {result}")
                processed_results.append(PDFParseResult(
                    source=sources[i],
                    success=False,
                    error=str(result),
                    timestamp=datetime.now().isoformat()
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _fetch_pdf(self, url: str) -> Optional[bytes]:
        """
        Загрузка PDF файла с retry механизмом.
        
        Выполняет до max_retries попыток с задержкой между ними.
        """
        session = await self._get_session()
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Попытка {attempt}/{self.max_retries} загрузки PDF: {url}")
                
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Попытка {attempt}: HTTP {response.status}")
                        if attempt < self.max_retries:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return None
                    
                    data = await response.read()
                    
                    # Проверка, что это действительно PDF
                    if not data[:5] == b'%PDF-':
                        logger.warning(f"Файл не является PDF: {url}")
                        return None
                    
                    logger.debug(f"PDF загружен: {len(data)} байт")
                    return data
            
            except asyncio.TimeoutError:
                logger.warning(f"Попытка {attempt}: таймаут загрузки PDF")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
            except aiohttp.ClientError as e:
                logger.warning(f"Попытка {attempt}: ошибка загрузки — {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Попытка {attempt}: непредвиденная ошибка — {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
        
        return None
    
    def _extract_from_pdf(
        self, pdf_bytes: bytes, source: PDFSource
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """
        Извлечение расписания из PDF файла.
        
        Пробует несколько стратегий:
        1. Извлечение таблиц через pdfplumber
        2. Парсинг текста через регулярные выражения
        """
        lessons: List[ScheduleLesson] = []
        groups: List[str] = []
        
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    logger.debug(f"Обработка страницы {page_num}/{len(pdf.pages)}")
                    
                    # Стратегия 1: Извлечение таблиц
                    tables = page.extract_tables({
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    })
                    
                    if tables:
                        for table in tables:
                            table_lessons, table_groups = self._parse_table(
                                table, source, page_num
                            )
                            lessons.extend(table_lessons)
                            groups.extend(table_groups)
                    
                    # Стратегия 2: Парсинг текста (если таблиц мало)
                    if len(tables) <= 1:
                        text = page.extract_text()
                        if text:
                            text_lessons, text_groups = self._parse_text(
                                text, source, page_num
                            )
                            # Добавляем только если из таблиц ничего не извлекли
                            if not tables:
                                lessons.extend(text_lessons)
                                groups.extend(text_groups)
        
        except Exception as e:
            logger.error(f"Ошибка обработки PDF: {e}", exc_info=True)
        
        # Убираем дубликаты групп
        groups = list(set(groups))
        
        return lessons, groups
    
    def _parse_table(
        self,
        table: List[List],
        source: PDFSource,
        page_num: int
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """
        Парсинг таблицы из PDF.
        
        Адаптируется под различные форматы таблиц расписания.
        """
        lessons: List[ScheduleLesson] = []
        groups: List[str] = []
        
        if not table or len(table) < 2:
            return lessons, groups
        
        # Определяем структуру таблицы
        # Обычно первая строка — заголовки (дни недели или группы)
        header = table[0]
        
        # Пытаемся определить, что в заголовке: дни недели или группы
        header_days = self._detect_days_in_header(header)
        header_groups = self._detect_groups_in_header(header)
        
        if header_days:
            # Таблица: строки = время/пары, столбцы = дни недели
            lessons, groups = self._parse_table_by_days(
                table, header_days, source
            )
        elif header_groups:
            # Таблица: строки = время/пары, столбцы = группы
            lessons, groups = self._parse_table_by_groups(
                table, header_groups, source
            )
        else:
            # Неизвестный формат — пробуем общий парсинг
            lessons, groups = self._parse_table_generic(table, source)
        
        return lessons, groups
    
    def _detect_days_in_header(self, header: List) -> Dict[int, str]:
        """Определение дней недели в заголовке таблицы"""
        days = {}
        for i, cell in enumerate(header):
            if cell is None:
                continue
            cell_text = str(cell).strip().lower()
            for day_name, pattern in DAY_PATTERNS.items():
                if re.search(pattern, cell_text, re.IGNORECASE):
                    days[i] = day_name
                    break
        return days
    
    def _detect_groups_in_header(self, header: List) -> Dict[int, str]:
        """Определение групп в заголовке таблицы"""
        groups = {}
        # Паттерн группы: буквы-цифры-цифры (например, ИС-201, ЛД-101)
        group_pattern = re.compile(
            r'[А-ЯA-Z]{2,5}[-\s]?\d{2,3}[-\s]?\d?'
        )
        
        for i, cell in enumerate(header):
            if cell is None:
                continue
            cell_text = str(cell).strip()
            match = group_pattern.search(cell_text)
            if match:
                groups[i] = match.group(0)
        
        return groups
    
    def _parse_table_by_days(
        self,
        table: List[List],
        days_map: Dict[int, str],
        source: PDFSource
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """Парсинг таблицы, где столбцы = дни недели"""
        lessons: List[ScheduleLesson] = []
        groups: List[str] = []
        
        for row_idx, row in enumerate(table[1:], 1):  # Пропускаем заголовок
            lesson_number = row_idx
            
            for col_idx, day_name in days_map.items():
                if col_idx >= len(row):
                    continue
                
                cell = row[col_idx]
                if cell is None or str(cell).strip() == "":
                    continue
                
                cell_text = str(cell).strip()
                
                # Извлекаем информацию из ячейки
                lesson = self._parse_cell_content(
                    cell_text, day_name, lesson_number, source
                )
                if lesson:
                    lessons.append(lesson)
        
        return lessons, groups
    
    def _parse_table_by_groups(
        self,
        table: List[List],
        groups_map: Dict[int, str],
        source: PDFSource
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """Парсинг таблицы, где столбцы = группы"""
        lessons: List[ScheduleLesson] = []
        groups = list(groups_map.values())
        
        # Определяем текущий день из контекста
        current_day = self._detect_current_day(table)
        
        for row_idx, row in enumerate(table[1:], 1):
            lesson_number = row_idx
            
            for col_idx, group_name in groups_map.items():
                if col_idx >= len(row):
                    continue
                
                cell = row[col_idx]
                if cell is None or str(cell).strip() == "":
                    continue
                
                cell_text = str(cell).strip()
                
                lesson = self._parse_cell_content(
                    cell_text, current_day, lesson_number, source,
                    group_override=group_name
                )
                if lesson:
                    lessons.append(lesson)
        
        return lessons, groups
    
    def _parse_table_generic(
        self,
        table: List[List],
        source: PDFSource
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """Общий парсинг таблицы с автоопределением структуры"""
        lessons: List[ScheduleLesson] = []
        groups: List[str] = []
        
        current_day = ""
        current_group = source.specialty or source.title
        
        for row in table:
            for cell in row:
                if cell is None:
                    continue
                
                cell_text = str(cell).strip()
                if not cell_text:
                    continue
                
                # Проверяем, является ли ячейка днём недели
                detected_day = self._detect_day_in_text(cell_text)
                if detected_day:
                    current_day = detected_day
                    continue
                
                # Проверяем, является ли ячейка группой
                detected_group = self._detect_group_in_text(cell_text)
                if detected_group:
                    current_group = detected_group
                    if current_group not in groups:
                        groups.append(current_group)
                    continue
                
                # Если это содержимое занятия
                if current_day and len(cell_text) > 3:
                    lesson = self._parse_cell_content(
                        cell_text, current_day, len(lessons) + 1, source,
                        group_override=current_group
                    )
                    if lesson:
                        lessons.append(lesson)
        
        return lessons, groups
    
    def _parse_cell_content(
        self,
        text: str,
        day: str,
        number: int,
        source: PDFSource,
        group_override: str = ""
    ) -> Optional[ScheduleLesson]:
        """
        Парсинг содержимого одной ячейки таблицы.
        
        Извлекает: предмет, тип, преподаватель, аудитория.
        """
        if not text or len(text.strip()) < 2:
            return None
        
        text = text.strip()
        
        # Определяем группу
        group = group_override or source.specialty or source.title
        
        # Определяем время
        time_start, time_end = LESSON_TIMES.get(number, ("", ""))
        
        # Извлекаем предмет
        subject = self._extract_subject(text)
        if not subject:
            return None
        
        # Определяем тип занятия
        lesson_type = self._detect_lesson_type(text)
        
        # Извлекаем преподавателя
        teacher = self._extract_teacher(text)
        
        # Извлекаем аудиторию
        room = self._extract_room(text)
        
        return ScheduleLesson(
            group=group,
            day=day,
            number=number,
            time=time_start,
            end_time=time_end,
            subject=subject,
            type=lesson_type,
            teacher=teacher,
            room=room,
            building=source.building,
            updated_at=datetime.now().isoformat()
        )
    
    def _parse_text(
        self,
        text: str,
        source: PDFSource,
        page_num: int
    ) -> Tuple[List[ScheduleLesson], List[str]]:
        """
        Парсинг текстового содержимого страницы PDF.
        
        Используется как резервный метод, когда таблицы не извлекаются.
        """
        lessons: List[ScheduleLesson] = []
        groups: List[str] = []
        
        current_day = ""
        current_group = source.specialty or source.title
        lesson_number = 0
        
        # Разбиваем текст на строки
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Проверяем, является ли строка днём недели
            detected_day = self._detect_day_in_text(line)
            if detected_day:
                current_day = detected_day
                lesson_number = 0
                continue
            
            # Проверяем, является ли строка группой
            detected_group = self._detect_group_in_text(line)
            if detected_group:
                current_group = detected_group
                if current_group not in groups:
                    groups.append(current_group)
                continue
            
            # Проверяем, содержит ли строка время (начало занятия)
            time_match = re.search(r'(\d{1,2}[.:]\d{2})', line)
            if time_match and current_day:
                lesson_number += 1
                time_str = time_match.group(1).replace('.', ':')
                
                subject = self._extract_subject(line)
                if subject:
                    lesson_type = self._detect_lesson_type(line)
                    teacher = self._extract_teacher(line)
                    room = self._extract_room(line)
                    
                    lessons.append(ScheduleLesson(
                        group=current_group,
                        day=current_day,
                        number=lesson_number,
                        time=time_str,
                        end_time="",
                        subject=subject,
                        type=lesson_type,
                        teacher=teacher,
                        room=room,
                        building=source.building,
                        updated_at=datetime.now().isoformat()
                    ))
        
        return lessons, groups
    
    def _detect_day_in_text(self, text: str) -> str:
        """Обнаружение дня недели в тексте"""
        for day_name, pattern in DAY_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return day_name
        return ""
    
    def _detect_group_in_text(self, text: str) -> str:
        """Обнаружение группы в тексте"""
        pattern = re.compile(r'([А-ЯA-Z]{2,5}[-\s]?\d{2,3}[-\s]?\d?)')
        match = pattern.search(text)
        return match.group(1) if match else ""
    
    def _detect_current_day(self, table: List[List]) -> str:
        """Определение текущего дня из контекста таблицы"""
        # Проверяем первые строки на наличие дня недели
        for row in table[:3]:
            for cell in row:
                if cell:
                    day = self._detect_day_in_text(str(cell))
                    if day:
                        return day
        return "Понедельник"  # По умолчанию
    
    def _extract_subject(self, text: str) -> str:
        """Извлечение названия предмета из текста ячейки"""
        # Удаляем время, номера аудиторий, ФИО преподавателя
        cleaned = text
        
        # Удаляем время
        cleaned = re.sub(r'\d{1,2}[.:]\d{2}\s*[-–—]\s*\d{1,2}[.:]\d{2}', '', cleaned)
        cleaned = re.sub(r'\d{1,2}[.:]\d{2}', '', cleaned)
        
        # Удаляем номера аудиторий
        cleaned = re.sub(r'ауд\.?\s*\d+[а-яА-Я]?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b\d{1,4}[а-я]?\s*(?:корп\.?|к\.?)', '', cleaned, flags=re.IGNORECASE)
        
        # Удаляем ФИО преподавателя
        cleaned = re.sub(
            r'[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\.?',
            '', cleaned
        )
        cleaned = re.sub(
            r'[А-Я]\.\s*[А-Я]\.\s*[А-Я][а-я]+',
            '', cleaned
        )
        
        # Удаляем типы занятий
        cleaned = re.sub(r'\b(?:лекц\.?|практ\.?|лаб\.?|экз\.?|конс\.?)\b', '', cleaned, flags=re.IGNORECASE)
        
        # Убираем лишние пробелы и спецсимволы
        cleaned = re.sub(r'[\s,;|/\\]+', ' ', cleaned).strip()
        cleaned = re.sub(r'^[\d\s.:-]+$', '', cleaned)  # Если остались только цифры/время
        
        # Берём первую значимую часть (до 80 символов)
        if cleaned and len(cleaned) > 2:
            return cleaned[:80]
        
        return ""
    
    def _detect_lesson_type(self, text: str) -> str:
        """Определение типа занятия по тексту"""
        text_lower = text.lower()
        
        if re.search(r'\b(?:лекц\.?|lecture)\b', text_lower):
            return 'lecture'
        elif re.search(r'\b(?:лаб\.?|лабораторн\w*|laboratory)\b', text_lower):
            return 'lab'
        elif re.search(r'\b(?:экз\.?|экзамен|exam)\b', text_lower):
            return 'exam'
        elif re.search(r'\b(?:зач[её]т|consul|конс\.?)\b', text_lower):
            return 'consultation'
        elif re.search(r'\b(?:практ\.?|practice|семин\w*)\b', text_lower):
            return 'practice'
        
        return 'practice'  # По умолчанию
    
    def _extract_teacher(self, text: str) -> str:
        """Извлечение ФИО преподавателя"""
        # Паттерн 1: Фамилия И.О.
        match = re.search(
            r'([А-Я][а-я]+)\s+([А-Я])\.\s*([А-Я])\.?',
            text
        )
        if match:
            return f"{match.group(1)} {match.group(2)}.{match.group(3)}."
        
        # Паттерн 2: И.О. Фамилия
        match = re.search(
            r'([А-Я])\.\s*([А-Я])\.\s+([А-Я][а-я]+)',
            text
        )
        if match:
            return f"{match.group(3)} {match.group(1)}.{match.group(2)}."
        
        return ""
    
    def _extract_room(self, text: str) -> str:
        """Извлечение номера аудитории"""
        # Паттерн: "ауд. 305" или просто "305"
        match = re.search(
            r'(?:ауд\.?\s*)?(\d{1,4}[а-яА-Я]?)',
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(1)
        return ""


async def test_pdf_parser():
    """Тестовый запуск PDF парсера"""
    from .html_parser import HTMLScheduleParser
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Сначала получаем список PDF файлов
    html_parser = HTMLScheduleParser()
    try:
        html_result = await html_parser.parse()
        
        if not html_result.success:
            print(f"Ошибка парсинга HTML: {html_result.error}")
            return
        
        print(f"Найдено {len(html_result.sources)} PDF файлов")
        
        # Парсим первый PDF файл
        if html_result.sources:
            pdf_parser = PDFScheduleParser()
            try:
                result = await pdf_parser.parse_source(html_result.sources[0])
                
                print(f"\n{'='*60}")
                print(f"Результат парсинга PDF: {'УСПЕХ' if result.success else 'ОШИБКА'}")
                print(f"Источник: {result.source.title}")
                
                if result.error:
                    print(f"Ошибка: {result.error}")
                
                print(f"Найдено занятий: {len(result.lessons)}")
                print(f"Найдено групп: {len(result.groups)}")
                
                for lesson in result.lessons[:5]:
                    print(f"\n  [{lesson.day}] #{lesson.number} {lesson.time}")
                    print(f"    Группа: {lesson.group}")
                    print(f"    Предмет: {lesson.subject} ({lesson.type})")
                    print(f"    Преподаватель: {lesson.teacher}")
                    print(f"    Аудитория: {lesson.room}")
                
                print(f"{'='*60}")
            
            finally:
                await pdf_parser.close()
    
    finally:
        await html_parser.close()


if __name__ == "__main__":
    asyncio.run(test_pdf_parser())
