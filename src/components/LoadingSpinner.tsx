/**
 * Анимированный индикатор загрузки
 */
export function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="relative">
        <div className="w-14 h-14 border-4 border-blue-100 dark:border-blue-900 rounded-full" />
        <div className="absolute top-0 left-0 w-14 h-14 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <svg className="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
      </div>
      <p className="mt-4 text-sm text-gray-500 dark:text-gray-400 font-medium">
        Загрузка расписания...
      </p>
    </div>
  );
}
