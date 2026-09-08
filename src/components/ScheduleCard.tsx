import { Lesson, LESSON_COLORS, LESSON_TYPE_LABELS } from '../types';

interface ScheduleCardProps {
  lesson: Lesson;
  isCurrent: boolean;
  isPast: boolean;
}

/**
 * Карточка одного занятия
 */
export function ScheduleCard({ lesson, isCurrent, isPast }: ScheduleCardProps) {
  const colors = LESSON_COLORS[lesson.type];

  return (
    <div
      className={`relative rounded-2xl border-l-4 p-4 transition-all duration-300 ${
        colors.bg
      } ${colors.darkBg} ${colors.border} ${colors.darkBorder} ${
        isCurrent
          ? 'ring-2 ring-blue-400 dark:ring-blue-500 shadow-lg shadow-blue-500/10 scale-[1.01]'
          : isPast
          ? 'opacity-50'
          : 'shadow-sm hover:shadow-md'
      }`}
    >
      {/* Индикатор текущей пары */}
      {isCurrent && (
        <div className="absolute -top-2 -right-2 flex items-center gap-1 bg-blue-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-lg animate-pulse">
          <span className="w-1.5 h-1.5 bg-white rounded-full" />
          СЕЙЧАС
        </div>
      )}

      {/* Индикатор изменения */}
      {lesson.isChanged && (
        <div className="absolute -top-2 left-4 flex items-center gap-1 bg-amber-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-lg">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          ИЗМЕНЕНО
        </div>
      )}

      <div className="flex items-start gap-3">
        {/* Время и номер пары */}
        <div className="flex flex-col items-center min-w-[52px]">
          <div className={`text-xs font-bold px-2 py-0.5 rounded-md ${colors.text} bg-white/60 dark:bg-black/20`}>
            {lesson.number} пара
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
            {lesson.startTime}
          </div>
          <div className="w-px h-4 bg-gray-300 dark:bg-gray-600 my-0.5" />
          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">
            {lesson.endTime}
          </div>
        </div>

        {/* Информация о занятии */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-gray-900 dark:text-white text-sm truncate">
              {lesson.subject}
            </h3>
            <span className={`shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-md ${colors.text} ${colors.bg} ${colors.darkBg} border ${colors.border} ${colors.darkBorder}`}>
              {LESSON_TYPE_LABELS[lesson.type]}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 mb-1">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span className="truncate">{lesson.teacher}</span>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span>Ауд. {lesson.room}</span>
            {lesson.building && (
              <span className="text-gray-400 dark:text-gray-500">• {lesson.building}</span>
            )}
          </div>

          {lesson.comment && (
            <div className="mt-2 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-2 py-1 rounded-lg">
              💬 {lesson.comment}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
