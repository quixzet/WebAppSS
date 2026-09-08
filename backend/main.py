"""
FastAPI приложение для расписания занятий
Основной сервер с API endpoints
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from database import Database
from scheduler import ScheduleScheduler
from parsers.html_parser import HTMLScheduleParser
from parsers.pdf_parser import PDFScheduleParser

# Модели данных (Pydantic)
from pydantic import BaseModel


class LessonModel(BaseModel):
    id: str
    number: int
    startTime: str
    endTime: str
    subject: str
    type: str  # lecture, practice, lab, exam, consultation
    teacher: str
    room: str
    building: Optional[str] = None
    isChanged: bool = False
    comment: Optional[str] = None


class DayScheduleModel(BaseModel):
    date: str
    dayOfWeek: str
    lessons: List[LessonModel]


class WeekScheduleModel(BaseModel):
    weekNumber: int
    days: List[DayScheduleModel]


class GroupModel(BaseModel):
    id: str
    name: str
    faculty: str
    course: int


class UpdateStatusModel(BaseModel):
    lastUpdate: str
    nextUpdate: str
    source: str
    success: bool


# Глобальные объекты
db = Database()
scheduler = ScheduleScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    db.initialize()
    scheduler.start(db)
    yield
    # Shutdown
    scheduler.stop()


# Создание приложения
app = FastAPI(
    title="Расписание занятий API",
    description="API для получения расписания занятий института",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware для Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === API Endpoints ===


@app.get("/api/groups", response_model=List[GroupModel])
async def get_groups():
    """Получить список всех групп"""
    groups = db.get_all_groups()
    return groups


@app.get("/api/schedule/{group_id}", response_model=WeekScheduleModel)
async def get_schedule(group_id: str, week: Optional[int] = None):
    """
    Получить расписание группы на текущую или указанную неделю.
    
    - group_id: ID группы
    - week: номер недели (необязательно, по умолчанию текущая)
    """
    schedule = db.get_schedule(group_id, week)
    if not schedule:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    return schedule


@app.get("/api/updates", response_model=UpdateStatusModel)
async def get_update_status():
    """Получить статус последнего обновления данных"""
    status = db.get_update_status()
    return status


@app.post("/api/schedule/refresh")
async def refresh_schedule():
    """Принудительное обновление расписания"""
    try:
        html_parser = HTMLScheduleParser()
        pdf_parser = PDFScheduleParser()
        
        # Парсинг HTML
        html_data = await html_parser.parse()
        if html_data:
            db.update_schedule(html_data)
        
        # Парсинг PDF
        pdf_data = await pdf_parser.parse()
        if pdf_data:
            db.update_schedule(pdf_data)
        
        db.set_update_status(success=True)
        return {"status": "ok", "message": "Расписание обновлено"}
    except Exception as e:
        db.set_update_status(success=False)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notifications/subscribe")
async def subscribe_notifications(chat_id: str, group_id: str):
    """Подписка на уведомления об изменениях расписания"""
    db.add_subscription(chat_id, group_id)
    return {"status": "ok", "message": "Подписка оформлена"}


@app.post("/api/notifications/unsubscribe")
async def unsubscribe_notifications(chat_id: str):
    """Отписка от уведомлений"""
    db.remove_subscription(chat_id)
    return {"status": "ok", "message": "Подписка отменена"}


# Монтирование статических файлов (фронтенд)
app.mount("/", StaticFiles(directory="../dist", html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
