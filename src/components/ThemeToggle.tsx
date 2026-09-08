import { useTheme } from '../hooks/useTheme';

/**
 * Компонент переключения темы
 */
export function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="relative w-14 h-7 rounded-full transition-all duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 dark:focus:ring-offset-gray-800"
      style={{
        background: isDark
          ? 'linear-gradient(135deg, #1e3a5f, #2d5a87)'
          : 'linear-gradient(135deg, #87CEEB, #4FC3F7)',
      }}
      aria-label={isDark ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
    >
      <div
        className={`absolute top-0.5 w-6 h-6 rounded-full transition-all duration-300 flex items-center justify-center text-sm shadow-md ${
          isDark
            ? 'left-7 bg-gray-800'
            : 'left-0.5 bg-white'
        }`}
      >
        {isDark ? '🌙' : '☀️'}
      </div>
    </button>
  );
}
