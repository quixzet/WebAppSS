import { useState, useEffect, useMemo } from 'react';
import { DaySchedule, ViewMode, WeekSchedule } from '../types';
import { mockSchedules, mockUpdateStatus } from '../data/mockData';

/**
 * Хук для работы с расписанием
 * В реальном приложении загружает данные с API
 */
export function useSchedule(groupId: string | null) {
  const [schedule, setSchedule] = useState<WeekSchedule | null>(null);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('day');
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [lastUpdate, setLastUpdate] = useState<string>('');

  // Загрузка расписания
  useEffect(() => {
    if (!groupId) {
      setSchedule(null);
      return;
    }

    setLoading(true);
    // Имитация загрузки с API
    const timer = setTimeout(() => {
      const data = mockSchedules[groupId] || null;
      setSchedule(data);
      setLastUpdate(mockUpdateStatus.lastUpdate);
      setLoading(false);

      // Устанавливаем текущий день
      if (data) {
        const today = new Date().toISOString().split('T')[0];
        const todayIndex = data.days.findIndex(d => d.date === today);
        setSelectedDayIndex(todayIndex >= 0 ? todayIndex : 0);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [groupId]);

  // Текущий день
  const currentDay: DaySchedule | null = useMemo(() => {
    if (!schedule) return null;
    return schedule.days[selectedDayIndex] || null;
  }, [schedule, selectedDayIndex]);

  // Определение текущей пары
  const currentLessonIndex = useMemo(() => {
    if (!currentDay) return -1;
    const now = new Date();
    const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    return currentDay.lessons.findIndex(lesson => {
      return currentTime >= lesson.startTime && currentTime < lesson.endTime;
    });
  }, [currentDay]);

  // Проверка, является ли день сегодняшним
  const isToday = useMemo(() => {
    if (!currentDay) return false;
    const today = new Date().toISOString().split('T')[0];
    return currentDay.date === today;
  }, [currentDay]);

  return {
    schedule,
    currentDay,
    currentLessonIndex,
    isToday,
    loading,
    viewMode,
    setViewMode,
    selectedDayIndex,
    setSelectedDayIndex,
    lastUpdate,
  };
}
