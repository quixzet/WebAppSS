import { useState, useEffect, useCallback } from 'react';

/**
 * Хук для управления темой (светлая/тёмная)
 * Поддерживает:
 * - Системные настройки
 * - localStorage
 * - Telegram WebApp цветовую схему
 */
export function useTheme() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    // Приоритет 1: Telegram WebApp
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      return window.Telegram.WebApp.colorScheme === 'dark';
    }
    
    // Приоритет 2: Сохранённая тема
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    
    // Приоритет 3: Системные настройки
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      root.classList.remove('light');
      root.setAttribute('data-theme', 'dark');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
      root.setAttribute('data-theme', 'light');
    }
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
  }, [isDark]);

  // Слушаем изменения темы от Telegram
  useEffect(() => {
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      const handler = () => {
        setIsDark(tg.colorScheme === 'dark');
      };
      tg.onEvent('themeChanged', handler);
      return () => {
        tg.offEvent('themeChanged', handler);
      };
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setIsDark(prev => !prev);
  }, []);

  return { isDark, toggleTheme };
}
