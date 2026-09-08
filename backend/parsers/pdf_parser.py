"""
Парсер PDF расписания
Использует pdfplumber для извлечения текста из PDF файлов
"""

import pdfplumber
import aiohttp
import re
import logging
from typing import List, Dict, Optional
from io import BytesIO
from datetime import datetime

logger = logging.getLogger(__name__)


class PDFScheduleParser:
    """
    Парсер PDF файлов с расписанием.
    
    Обрабатывает PDF файлы, загруженные на сайт института,
    извлекает структурированные данные о занятиях.
    """
    
    def __init__(
        self,
        pdf_url: str = "https://example-university.ru/schedule/schedule.pdf",
    ):
        self.pdf_url = pdf_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def parse(self) -> Optional[List[Dict]]:
        """
        Основная функция парсинга PDF.
        Загружает PDF и извлекает расписание.
        """
        try:
            session = await self._get_session()
            
            # Загрузка PDF
            async with session.get(self.pdf_url) as response:
                if response.status != 200:
                    logger.error(f"Ошибка загрузки PDF: {response.status}")
                    return None
                
                pdf_bytes = await response.read()
            
            # Обработка PDF
            schedules = self._extract_from_pdf(pdf_bytes)
            
            logger.info(f"Из PDF извлечено {len(schedules)} групп")
            return schedules
            
        except Exception as e:
            logger.error(f"Ошибка парсинга PDF: {e}")
            return None
    
    def _extract_from_pdf(self, pdf_bytes: bytes) -> List[Dict]:
        """Извлечение данных из PDF файла"""
        schedules = []
        
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    # Извлечение текста
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    # Извлечение таблиц (если есть)
                    tables = page.extract_tables()
                    
                    # Парсинг текста страницы
                    page_data = self._parse_page_text(text)
                    if page_data:
                        schedules.extend(page_data)
                    
                    # Парсинг таблиц
                    for table in tables:
                        table_data = self._parse_table(table)
                        if table_data:
                            schedules.extend(table_data)
        
        except Exception as e:
            logger.error(f"Ошибка обработки PDF: {e}")
        
        return schedules
    
    def _parse_page_text(self, text: str) -> List[Dict]:
        """
        Парсинг текстового содержимого страницы PDF.
        Использует регулярные выражения для извлечения данных.
        """
        schedules = []
        
        # Разделение по группам
        # Пример паттерна: "Группа ИСП-21-1" или "ИСП-21-1"
        group_pattern = r'(?:Группа\s+)?([А-Я]{2,4}-\d{2}-\d)'
        groups = re.split(group_pattern, text)
        
        for i in range(1, len(groups), 2):
            if i + 1 < len(groups):
                group_name = groups[i].strip()
                group_text = groups[i + 1]
                
                schedule = self._parse_group_text(group_name, group_text)
                if schedule:
                    schedules.append(schedule)
        
        return schedules
    
    def _parse_group_text(self, group_name: str, text: str) -> Optional[Dict]:
        """Парсинг текста расписания одной группы"""
        days = []
        
        # Паттерны дней недели
        day_patterns = {
            'Понедельник': r'Понедельник|Пн',
            'Вторник': r'Вторник|Вт',
            'Среда': r'Среда|Ср',
            'Четверг': r'Четверг|Чт',
            'Пятница': r'Пятница|Пт',
            'Суббота': r'Суббота|Сб',
        }
        
        for day_name, pattern in day_patterns.items():
            day_match = re.search(pattern, text)
            if day_match:
                # Извлечение занятий для этого дня
                day_text = text[day_match.end():]
                # Ограничение до следующего дня
                next_day = re.search(r'|'.join(day_patterns.values()), day_text)
                if next_day:
                    day_text = day_text[:next_day.start()]
                
                lessons = self._parse_day_lessons(day_text)
                if lessons:
                    days.append({
                        'dayOfWeek': day_name,
                        'lessons': lessons,
                    })
        
        if not days:
            return None
        
        return {
            'group': group_name,
            'week': {'days': days},
        }
    
    def _parse_day_lessons(self, text: str) -> List[Dict]:
        """Парсинг занятий одного дня"""
        lessons = []
        
        # Паттерн для времени: "08:30 - 10:00" или "8.30-10.00"
        time_pattern = r'(\d{1,2}[.:]\d{2})\s*[-–]\s*(\d{1,2}[.:]\d{2})'
        
        # Разбиение по номерам пар
        parts = re.split(r'(\d)\.\s', text)
        
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                number = int(parts[i])
                lesson_text = parts[i + 1]
                
                # Извлечение времени
                time_match = re.search(time_pattern, lesson_text)
                start_time = end_time = ""
                if time_match:
                    start_time = time_match.group(1).replace('.', ':')
                    end_time = time_match.group(2).replace('.', ':')
                
                # Извлечение предмета
                subject = self._extract_subject(lesson_text)
                
                # Извлечение преподавателя
                teacher = self._extract_teacher(lesson_text)
                
                # Извлечение аудитории
                room = self._extract_room(lesson_text)
                
                # Определение типа
                lesson_type = self._detect_type(lesson_text)
                
                if subject:
                    lessons.append({
                        'number': number,
                        'startTime': start_time,
                        'endTime': end_time,
                        'subject': subject,
                        'type': lesson_type,
                        'teacher': teacher,
                        'room': room,
                    })
        
        return lessons
    
    def _parse_table(self, table: List[List]) -> List[Dict]:
        """Парсинг табличных данных из PDF"""
        # Адаптировать под конкретную структуру таблицы
        return []
    
    def _extract_subject(self, text: str) -> str:
        """Извлечение названия предмета"""
        # Удаляем время и номера аудиторий
        cleaned = re.sub(r'\d{1,2}[.:]\d{2}\s*[-–]\s*\d{1,2}[.:]\d{2}', '', text)
        cleaned = re.sub(r'ауд\.?\s*\d+', '', cleaned)
        cleaned = re.sub(r'\d+\s*корп\.?', '', cleaned)
        return cleaned.strip()[:100]
    
    def _extract_teacher(self, text: str) -> str:
        """Извлечение ФИО преподавателя"""
        # Паттерн для ФИО: Фамилия И.О. или Фамилия И. О.
        pattern = r'([А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\.?|[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\.)'
        match = re.search(pattern, text)
        return match.group(0) if match else ""
    
    def _extract_room(self, text: str) -> str:
        """Извлечение номера аудитории"""
        pattern = r'(?:ауд\.?\s*)?(\d{1,4}[а-я]?)'
        match = re.search(pattern, text)
        return match.group(1) if match else ""
    
    def _detect_type(self, text: str) -> str:
        """Определение типа занятия"""
        text_lower = text.lower()
        if 'лекц' in text_lower:
            return 'lecture'
        elif 'лаб' in text_lower:
            return 'lab'
        elif 'экз' in text_lower or 'зач' in text_lower:
            return 'exam'
        elif 'конс' in text_lower:
            return 'consultation'
        else:
            return 'practice'
    
    async def get_pdf_urls(self) -> List[str]:
        """Получение списка URL PDF файлов с расписанием"""
        try:
            session = await self._get_session()
            # Загрузка страницы со списком PDF
            # ...
            return [self.pdf_url]
        except Exception as e:
            logger.error(f"Ошибка получения списка PDF: {e}")
            return []
