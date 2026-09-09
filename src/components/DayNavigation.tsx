interface DayNavigationProps {
  currentDayIndex: number;
  totalDays: number;
  onPrevious: () => void;
  onNext: () => void;
  onToday: () => void;
  isToday: boolean;
}

/**
 * Навигация по дням (вперёд/назад)
 */
export function DayNavigation({ currentDayIndex, totalDays, onPrevious, onNext, onToday, isToday }: DayNavigationProps) {
  return (
    <div className="flex items-center justify-between px-1">
      <button
        onClick={onPrevious}
        disabled={currentDayIndex === 0}
        className="w-10 h-10 flex items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all active:scale-95"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {!isToday && (
        <button
          onClick={onToday}
          className="px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
        >
          Сегодня
        </button>
      )}

      <button
        onClick={onNext}
        disabled={currentDayIndex === totalDays - 1}
        className="w-10 h-10 flex items-center justify-center rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all active:scale-95"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}
