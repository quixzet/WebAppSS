"""
Парсер HTML расписания с сайта института
Использует BeautifulSoup для извлечения данных
"""

import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class HTMLScheduleParser:
    """
    Парсер интерактивного расписания с сайта института.
    
    Адаптируется под конкретную структуру HTML страницы.
    URL и селекторы настраиваются через конструктор.
    """
    
    def __init__(
        self,
        base_url: str = "https://example-university.ru/schedule",
        schedule_url: str = "https://example-university.ru/schedule/api",
    ):
        self.base_url = base_url
        self.schedule_url = schedule_url
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
        Основная функция парсинга.
        Возвращает список расписаний по группам.
        """
        try:
            session = await self._get_session()
            
            # Загрузка страницы с расписанием
            async with session.get(self.schedule_url) as response:
                if response.status != 200:
                    logger.error(f"Ошибка загрузки: {response.status}")
                    return None
                
                html = await response.text()
            
            # Парсинг HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлечение данных (адаптировать под конкретный сайт)
            schedules = self._extract_schedules(soup)
            
            logger.info(f"Спарсено {len(schedules)} групп")
            return schedules
            
        except Exception as e:
            logger.error(f"Ошибка парсинга HTML: {e}")
            return None
    
    def _extract_schedules(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Извлечение расписаний из HTML.
        
        Структура должна быть адаптирована под конкретный сайт института.
        Ниже приведён примерный шаблон.
        """
        schedules = []
        
        # Пример: поиск таблицы расписания
        # schedule_table = soup.find('table', class_='schedule-table')
        # if not schedule_table:
        #     return schedules
        
        # Пример: извлечение групп
        # groups = soup.find_all('div', class_='group-name')
        # for group_elem in groups:
        #     group_name = group_elem.text.strip()
        #     group_schedule = self._parse_group_schedule(group_elem)
        #     schedules.append({
        #         'group': group_name,
        #         'week': group_schedule
        #     })
        
        return schedules
    
    def _parse_group_schedule(self, element) -> Dict:
        """Парсинг расписания одной группы"""
        days = []
        
        # Пример структуры:
        # day_elements = element.find_all('div', class_='day')
        # for day_elem in day_elements:
        #     day_name = day_elem.find('h3').text.strip()
        #     lessons = []
        #     lesson_elements = day_elem.find_all('div', class_='lesson')
        #     for lesson_elem in lesson_elements:
        #         lesson = {
        #             'number': int(lesson_elem.get('data-number', 0)),
        #             'time': lesson_elem.find('span', class_='time').text.strip(),
        #             'subject': lesson_elem.find('span', class_='subject').text.strip(),
        #             'type': self._detect_lesson_type(lesson_elem),
        #             'teacher': lesson_elem.find('span', class_='teacher').text.strip(),
        #             'room': lesson_elem.find('span', class_='room').text.strip(),
        #         }
        #         lessons.append(lesson)
        #     days.append({
        #         'dayOfWeek': day_name,
        #         'lessons': lessons
        #     })
        
        return {'days': days}
    
    def _detect_lesson_type(self, element) -> str:
        """Определение типа занятия по CSS классам или тексту"""
        classes = element.get('class', [])
        text = element.text.lower()
        
        if 'lecture' in classes or 'лекц' in text:
            return 'lecture'
        elif 'practice' in classes or 'практ' in text:
            return 'practice'
        elif 'lab' in classes or 'лаб' in text:
            return 'lab'
        elif 'exam' in classes or 'экз' in text:
            return 'exam'
        else:
            return 'practice'  # По умолчанию
    
    async def parse_groups_list(self) -> List[Dict]:
        """Получение списка всех групп"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/groups") as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                groups = []
                # group_elements = soup.find_all('option', class_='group')
                # for elem in group_elements:
                #     groups.append({
                #         'id': elem.get('value'),
                #         'name': elem.text.strip()
                #     })
                
                return groups
                
        except Exception as e:
            logger.error(f"Ошибка получения списка групп: {e}")
            return []
