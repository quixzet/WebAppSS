"""
Парсер HTML страницы расписания с сайта СИЭУиП (https://sielom.ru/schedule)

Структура страницы:
- .schedule-data — контейнер формы обучения (Очная/Заочная/ОЗФО)
- .title — заголовок формы обучения
- .schedule-columns — контейнер с колонками корпусов
- .column — колонка корпуса
- .column-head — заголовок корпуса (.coll-name, .coll-caption)
- .files — список PDF файлов
- .files a — ссылка на PDF файл с текстом-описанием

Основная задача парсера — извлечь все ссылки на PDF файлы
и передать их в pdf_parser для дальнейшего разбора.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Базовый URL сайта
BASE_URL = "https://sielom.ru"
SCHEDULE_URL = f"{BASE_URL}/schedule"

# User-Agent для имитации браузера (чтобы не блокировали)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Максимальное количество попыток при ошибке
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды


@dataclass
class PDFSource:
    """Модель источника PDF файла расписания"""
    url: str                          # Полный URL PDF файла
    title: str                        # Название (например, "1 курсы ЛД, СД, Ф")
    building: str = ""                # Корпус (например, "Корпус №1 и №6")
    building_address: str = ""        # Адрес корпуса
    education_form: str = ""          # Форма обучения (Очная/Заочная/ОЗФО)
    specialty: str = ""               # Специальность (определяется из title)
    
    @property
    def full_title(self) -> str:
        """Полное название с информацией о корпусе"""
        parts = [self.title]
        if self.building:
            parts.append(f"({self.building})")
        return " ".join(parts)


@dataclass
class ParseResult:
    """Результат парсинга HTML страницы"""
    success: bool
    sources: List[PDFSource] = field(default_factory=list)
    error: str = ""
    timestamp: str = ""


class HTMLScheduleParser:
    """
    Парсер HTML страницы расписания с сайта СИЭУиП.
    
    Извлекает ссылки на PDF файлы с расписанием,
    организованные по корпусам и формам обучения.
    """
    
    def __init__(
        self,
        url: str = SCHEDULE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = MAX_RETRIES,
        retry_delay: int = RETRY_DELAY,
    ):
        self.url = url
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.user_agent}
            )
        return self._session
    
    async def close(self):
        """Закрыть HTTP сессию"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def parse(self) -> ParseResult:
        """
        Основная функция парсинга HTML страницы.
        
        Returns:
            ParseResult с найденными PDF источниками или ошибкой.
        """
        from datetime import datetime
        
        logger.info(f"Начало парсинга HTML страницы: {self.url}")
        
        # Загрузка HTML с retry механизмом
        html_content = await self._fetch_with_retry()
        
        if html_content is None:
            return ParseResult(
                success=False,
                error="Не удалось загрузить HTML страницу после нескольких попыток",
                timestamp=datetime.now().isoformat()
            )
        
        # Парсинг HTML
        try:
            sources = self._extract_pdf_sources(html_content)
            
            if not sources:
                return ParseResult(
                    success=False,
                    error="На странице не найдено PDF файлов с расписанием. "
                          "Возможно, изменилась структура HTML.",
                    timestamp=datetime.now().isoformat()
                )
            
            logger.info(f"Найдено {len(sources)} PDF источников расписания")
            
            return ParseResult(
                success=True,
                sources=sources,
                timestamp=datetime.now().isoformat()
            )
        
        except Exception as e:
            logger.error(f"Ошибка парсинга HTML: {e}", exc_info=True)
            return ParseResult(
                success=False,
                error=f"Ошибка парсинга: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    async def _fetch_with_retry(self) -> Optional[str]:
        """
        Загрузка HTML страницы с механизмом повторных попыток.
        
        Выполняет до max_retries попыток с задержкой между ними.
        Обрабатывает кодировку UTF-8.
        """
        session = await self._get_session()
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Попытка {attempt}/{self.max_retries} загрузки {self.url}")
                
                async with session.get(self.url) as response:
                    # Проверка статуса ответа
                    if response.status != 200:
                        logger.warning(
                            f"Попытка {attempt}: HTTP статус {response.status}"
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return None
                    
                    # Чтение с правильной кодировкой
                    # Явно указываем UTF-8, так как сайт может не отдавать charset
                    raw_bytes = await response.read()
                    
                    # Пробуем определить кодировку из headers
                    content_type = response.headers.get('Content-Type', '')
                    if 'charset' in content_type.lower():
                        # Извлекаем charset из Content-Type
                        for part in content_type.split(';'):
                            part = part.strip()
                            if part.lower().startswith('charset='):
                                encoding = part.split('=')[1].strip().strip('"\'')
                                try:
                                    return raw_bytes.decode(encoding)
                                except (UnicodeDecodeError, LookupError):
                                    pass
                    
                    # По умолчанию UTF-8
                    try:
                        return raw_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        # Fallback на cp1251 (часто используется на российских сайтах)
                        logger.warning("UTF-8 декодирование не удалось, пробуем cp1251")
                        return raw_bytes.decode('cp1251', errors='replace')
            
            except asyncio.TimeoutError:
                logger.warning(f"Попытка {attempt}: таймаут соединения")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
            except aiohttp.ClientError as e:
                logger.warning(f"Попытка {attempt}: ошибка клиента — {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Попытка {attempt}: непредвиденная ошибка — {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"Все {self.max_retries} попыток загрузки не удались")
        return None
    
    def _extract_pdf_sources(self, html: str) -> List[PDFSource]:
        """
        Извлечение PDF источников из HTML страницы.
        
        Парсит структуру:
        .schedule-data > .title (форма обучения)
        .schedule-data > .schedule-columns > .column > .column-head + .files > a
        """
        sources: List[PDFSource] = []
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Находим все блоки с расписанием (по формам обучения)
        schedule_blocks = soup.find_all('div', class_='schedule-data')
        
        if not schedule_blocks:
            # Fallback: пробуем найти .schedule-columns напрямую
            schedule_blocks = soup.find_all('div', class_='schedule-columns')
            if schedule_blocks:
                # Оборачиваем в фиктивный блок
                logger.warning("Не найдены .schedule-data, используем .schedule-columns напрямую")
        
        for block in schedule_blocks:
            # Определяем форму обучения
            title_elem = block.find('div', class_='title')
            education_form = title_elem.get_text(strip=True) if title_elem else "Неизвестно"
            
            # Находим все колонки (корпуса)
            columns = block.find_all('div', class_='column')
            
            for column in columns:
                # Извлекаем информацию о корпусе
                building = ""
                building_address = ""
                
                head = column.find('div', class_='column-head')
                if head:
                    name_elem = head.find('div', class_='coll-name')
                    addr_elem = head.find('div', class_='coll-caption')
                    
                    building = name_elem.get_text(strip=True) if name_elem else ""
                    building_address = addr_elem.get_text(strip=True) if addr_elem else ""
                
                # Находим все PDF файлы
                files_container = column.find('div', class_='files')
                if not files_container:
                    continue
                
                links = files_container.find_all('a', href=True)
                
                for link in links:
                    href = link.get('href', '').strip()
                    
                    # Проверяем, что это PDF файл
                    if not href.lower().endswith('.pdf'):
                        continue
                    
                    # Формируем полный URL
                    if href.startswith('/'):
                        full_url = f"{BASE_URL}{href}"
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = f"{BASE_URL}/{href}"
                    
                    # Извлекаем название из текста ссылки
                    p_elem = link.find('p')
                    title = p_elem.get_text(strip=True) if p_elem else link.get_text(strip=True)
                    
                    if not title:
                        title = "Без названия"
                    
                    # Определяем специальность из названия
                    specialty = self._detect_specialty(title)
                    
                    source = PDFSource(
                        url=full_url,
                        title=title,
                        building=building,
                        building_address=building_address,
                        education_form=education_form,
                        specialty=specialty,
                    )
                    
                    sources.append(source)
                    logger.debug(f"Найден PDF: {title} → {full_url}")
        
        return sources
    
    def _detect_specialty(self, title: str) -> str:
        """
        Определение специальности по названию PDF файла.
        
        Маппинг известных специальностей СИЭУиП.
        """
        title_lower = title.lower()
        
        # Маппинг ключевых слов → специальность
        specialty_map = {
            'лечебное дело': 'Лечебное дело',
            'лд': 'Лечебное дело',
            'сестринское дело': 'Сестринское дело',
            'сд': 'Сестринское дело',
            'фармац': 'Фармация',
            'фарм': 'Фармация',
            'ф': 'Фармация',
            'юриспруденц': 'Юриспруденция',
            'правовед': 'Юриспруденция',
            'правоохранит': 'Правоохранительная деятельность',
            'пд': 'Правоохранительная деятельность',
            'физическ': 'Физическая культура',
            'фк': 'Физическая культура',
            'социальн': 'Социальная работа',
            'ср': 'Социальная работа',
            'технологи': 'Технология индустрии красоты',
            'тик': 'Технология индустрии красоты',
            'индустри': 'Технология индустрии красоты',
            'экономик': 'Экономика и бухгалтерский учет',
            'бухгалтер': 'Экономика и бухгалтерский учет',
            'эбу': 'Экономика и бухгалтерский учет',
            'банковск': 'Банковское дело',
            'бд': 'Банковское дело',
            'электромонт': 'Электромонтер по ремонту и обслуживанию',
            'электро': 'Электромонтер по ремонту и обслуживанию',
            'торгов': 'Торговое дело',
            'тд': 'Торговое дело',
            'информаци': 'Информационные системы и программирование',
            'программ': 'Разработка и управление программным обеспечением',
            'рупо': 'Разработка и управление программным обеспечением',
            'исп': 'Информационные системы и программирование',
            'ис': 'Информационные системы и программирование',
            'нала': 'Наладчик компьютерных сетей',
            'сетев': 'Сетевое и системное администрирование',
            'сса': 'Сетевое и системное администрирование',
            'дизай': 'Дизайн',
            'графическ': 'Графический дизайн',
            'гд': 'Графический дизайн',
            '1 курс': '1 курс',
            '2 курс': '2 курс',
            '3 курс': '3 курс',
            '4 курс': '4 курс',
        }
        
        for keyword, specialty in specialty_map.items():
            if keyword in title_lower:
                return specialty
        
        return title  # Если не нашли — возвращаем исходное название


async def test_parser():
    """Тестовый запуск парсера"""
    logging.basicConfig(level=logging.DEBUG)
    
    parser = HTMLScheduleParser()
    try:
        result = await parser.parse()
        
        print(f"\n{'='*60}")
        print(f"Результат парсинга: {'УСПЕХ' if result.success else 'ОШИБКА'}")
        print(f"Время: {result.timestamp}")
        
        if result.error:
            print(f"Ошибка: {result.error}")
        
        print(f"Найдено источников: {len(result.sources)}")
        
        for i, source in enumerate(result.sources, 1):
            print(f"\n--- Источник #{i} ---")
            print(f"  Название: {source.title}")
            print(f"  Специальность: {source.specialty}")
            print(f"  Форма обучения: {source.education_form}")
            print(f"  Корпус: {source.building}")
            print(f"  Адрес: {source.building_address}")
            print(f"  URL: {source.url}")
        
        print(f"{'='*60}")
        
    finally:
        await parser.close()


if __name__ == "__main__":
    asyncio.run(test_parser())
