/**
 * Хук для интеграции с Telegram WebApp API
 * Предоставляет методы для взаимодействия с Telegram
 */

import { useEffect, useCallback } from 'react';

interface TelegramWebApp {
  expand: () => void;
  ready: () => void;
  close: () => void;
  MainButton: {
    text: string;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
    setText: (text: string) => void;
  };
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  onEvent: (eventType: string, callback: () => void) => void;
  offEvent: (eventType: string, callback: () => void) => void;
  sendData: (data: string) => void;
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy') => void;
    notificationOccurred: (type: 'success' | 'warning' | 'error') => void;
    selectionChanged: () => void;
  };
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

export function useTelegram() {
  const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : null;
  const isTelegram = !!tg;

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
    }
  }, [tg]);

  const sendData = useCallback((data: Record<string, unknown>) => {
    if (tg) {
      tg.sendData(JSON.stringify(data));
    }
  }, [tg]);

  const hapticFeedback = useCallback((type: 'impact' | 'notification' | 'selection') => {
    if (tg?.HapticFeedback) {
      switch (type) {
        case 'impact':
          tg.HapticFeedback.impactOccurred('light');
          break;
        case 'notification':
          tg.HapticFeedback.notificationOccurred('success');
          break;
        case 'selection':
          tg.HapticFeedback.selectionChanged();
          break;
      }
    }
  }, [tg]);

  return {
    tg,
    isTelegram,
    sendData,
    hapticFeedback,
    colorScheme: tg?.colorScheme || 'light',
  };
}
