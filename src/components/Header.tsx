import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  lastUpdate?: string;
}

/**
 * Шапка приложения
 */
export function Header({ lastUpdate }: HeaderProps) {
  const formatTime = (iso: string) => {
    try {
      const date = new Date(iso);
      return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/80 dark:bg-gray-900/80 border-b border-gray-200 dark:border-gray-700/50 shadow-sm">
      <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center shadow-lg shadow-blue-500/25">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white leading-tight">
              Расписание
            </h1>
            {lastUpdate && (
              <p className="text-[10px] text-gray-400 dark:text-gray-500 leading-tight">
                обновлено в {formatTime(lastUpdate)}
              </p>
            )}
          </div>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
