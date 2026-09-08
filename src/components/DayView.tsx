import { DaySchedule } from '../types';
import { ScheduleCard } from './ScheduleCard';

interface DayViewProps {
  day: DaySchedule;
  currentLessonIndex: number;
  isToday: boolean;
}

/**
 * Просмотр расписания на день
 */
export function DayView({ day, currentLessonIndex, isToday }: DayViewProps) {
  const now = new Date();
  const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
    });
  };

  return (
    <div className="space-y-4">
      {/* Заголовок дня */}
      <div className="flex items-center justify-between px-1">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">
            {day.dayOfWeek}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {formatDate(day.date)}
            {isToday && (
              <span className="ml-2 inline-flex items-center gap-1 text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full font-medium">
                Сегодня
              </span>
            )}
          </p>
        </div>
        {isToday && (
          <div className="text-right">
            <p className="text-xs text-gray-400 dark:text-gray-500">Текущее время</p>
            <p className="text-sm font-mono font-bold text-gray-700 dark:text-gray-300">
              {currentTime}
            </p>
          </div>
        )}
      </div>

      {/* Занятия */}
      {day.lessons.length > 0 ? (
        <div className="space-y-3">
          {day.lessons.map((lesson, index) => (
            <ScheduleCard
              key={lesson.id}
              lesson={lesson}
              isCurrent={isToday && index === currentLessonIndex}
              isPast={isToday && index < currentLessonIndex}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="text-5xl mb-4">🎉</div>
          <p className="text-gray-500 dark:text-gray-400 font-medium">
            Нет занятий
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            Свободный день!
          </p>
        </div>
      )}

      {/* Статистика дня */}
      {day.lessons.length > 0 && (
        <div className="flex items-center justify-center gap-4 pt-2 text-xs text-gray-400 dark:text-gray-500">
          <span>{day.lessons.length} {day.lessons.length === 1 ? 'пара' : day.lessons.length < 5 ? 'пары' : 'пар'}</span>
          <span>•</span>
          <span>
            {day.lessons[0].startTime} — {day.lessons[day.lessons.length - 1].endTime}
          </span>
        </div>
      )}
    </div>
  );
}
