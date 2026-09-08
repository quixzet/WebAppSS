import { WeekSchedule } from '../types';

interface WeekViewProps {
  schedule: WeekSchedule;
  selectedDayIndex: number;
  onSelectDay: (index: number) => void;
  currentLessonIndex: number;
}

/**
 * Просмотр расписания на неделю
 */
export function WeekView({ schedule, selectedDayIndex, onSelectDay, currentLessonIndex }: WeekViewProps) {
  const today = new Date().toISOString().split('T')[0];

  const getDayShort = (dayOfWeek: string) => {
    const map: Record<string, string> = {
      'Понедельник': 'Пн',
      'Вторник': 'Вт',
      'Среда': 'Ср',
      'Четверг': 'Чт',
      'Пятница': 'Пт',
      'Суббота': 'Сб',
    };
    return map[dayOfWeek] || dayOfWeek.slice(0, 2);
  };

  const getDateShort = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.getDate();
  };

  const isCurrentDay = (dateStr: string) => dateStr === today;

  return (
    <div className="space-y-4">
      {/* Навигация по дням недели */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 scrollbar-hide px-1">
        {schedule.days.map((day, index) => {
          const isSelected = index === selectedDayIndex;
          const isToday = isCurrentDay(day.date);
          const hasLessons = day.lessons.length > 0;
          const hasChanges = day.lessons.some(l => l.isChanged);

          return (
            <button
              key={day.date}
              onClick={() => onSelectDay(index)}
              className={`flex flex-col items-center min-w-[52px] py-2 px-2 rounded-xl transition-all duration-200 ${
                isSelected
                  ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/25'
                  : isToday
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                  : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              <span className={`text-[10px] font-medium uppercase ${
                isSelected ? 'text-blue-100' : ''
              }`}>
                {getDayShort(day.dayOfWeek)}
              </span>
              <span className={`text-lg font-bold leading-tight ${
                isSelected ? '' : isToday ? 'font-extrabold' : ''
              }`}>
                {getDateShort(day.date)}
              </span>
              {/* Индикаторы */}
              <div className="flex items-center gap-0.5 mt-0.5 h-2">
                {hasLessons && (
                  <div className={`w-1 h-1 rounded-full ${
                    isSelected ? 'bg-white' : 'bg-gray-400 dark:bg-gray-500'
                  }`} />
                )}
                {hasChanges && (
                  <div className={`w-1 h-1 rounded-full ${
                    isSelected ? 'bg-amber-300' : 'bg-amber-400'
                  }`} />
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Расписание выбранного дня */}
      <div className="space-y-3">
        {schedule.days[selectedDayIndex]?.lessons.length > 0 ? (
          schedule.days[selectedDayIndex].lessons.map((lesson, index) => {
            const isCurrentDay = selectedDayIndex === schedule.days.findIndex(d => d.date === today);
            const colors = {
              lecture: { bg: 'bg-blue-50 dark:bg-blue-900/30', border: 'border-blue-400 dark:border-blue-500', text: 'text-blue-700 dark:text-blue-300' },
              practice: { bg: 'bg-green-50 dark:bg-green-900/30', border: 'border-green-400 dark:border-green-500', text: 'text-green-700 dark:text-green-300' },
              lab: { bg: 'bg-purple-50 dark:bg-purple-900/30', border: 'border-purple-400 dark:border-purple-500', text: 'text-purple-700 dark:text-purple-300' },
              exam: { bg: 'bg-red-50 dark:bg-red-900/30', border: 'border-red-400 dark:border-red-500', text: 'text-red-700 dark:text-red-300' },
              consultation: { bg: 'bg-amber-50 dark:bg-amber-900/30', border: 'border-amber-400 dark:border-amber-500', text: 'text-amber-700 dark:text-amber-300' },
            };
            const color = colors[lesson.type];
            const isCurrent = isCurrentDay && index === currentLessonIndex;
            const isPast = isCurrentDay && index < currentLessonIndex;

            return (
              <div
                key={lesson.id}
                className={`relative rounded-xl border-l-4 p-3 transition-all duration-300 ${color.bg} ${color.border} ${
                  isCurrent ? 'ring-2 ring-blue-400 dark:ring-blue-500 shadow-md' : isPast ? 'opacity-50' : 'shadow-sm'
                }`}
              >
                {isCurrent && (
                  <div className="absolute -top-1.5 -right-1.5 flex items-center gap-0.5 bg-blue-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full animate-pulse">
                    <span className="w-1 h-1 bg-white rounded-full" />
                    LIVE
                  </div>
                )}
                {lesson.isChanged && (
                  <div className="absolute -top-1.5 left-3 text-amber-500 text-xs">⚠️</div>
                )}
                <div className="flex items-center gap-3">
                  <div className="text-center min-w-[44px]">
                    <div className={`text-[10px] font-bold ${color.text}`}>
                      {lesson.number} п.
                    </div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400 font-mono">
                      {lesson.startTime}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-gray-900 dark:text-white truncate">
                      {lesson.subject}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {lesson.teacher} • ауд. {lesson.room}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="text-center py-8">
            <div className="text-4xl mb-2">🌴</div>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Нет занятий</p>
          </div>
        )}
      </div>
    </div>
  );
}
