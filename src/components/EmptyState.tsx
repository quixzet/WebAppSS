/**
 * Компонент "Нет занятий" (пустое состояние)
 */
interface EmptyStateProps {
  type?: 'no-group' | 'no-schedule' | 'no-lessons' | 'weekend';
}

export function EmptyState({ type = 'no-group' }: EmptyStateProps) {
  const configs = {
    'no-group': {
      emoji: '👆',
      title: 'Выберите группу',
      subtitle: 'для просмотра расписания',
    },
    'no-schedule': {
      emoji: '📋',
      title: 'Расписание не найдено',
      subtitle: 'Попробуйте выбрать другую группу',
    },
    'no-lessons': {
      emoji: '🎉',
      title: 'Нет занятий',
      subtitle: 'Свободный день!',
    },
    'weekend': {
      emoji: '🌴',
      title: 'Выходные',
      subtitle: 'Отдыхайте!',
    },
  };

  const config = configs[type];

  return (
    <div className="text-center py-12 animate-in">
      <div className="text-6xl mb-4 animate-bounce">{config.emoji}</div>
      <p className="text-gray-700 dark:text-gray-300 font-semibold text-lg">
        {config.title}
      </p>
      <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
        {config.subtitle}
      </p>
    </div>
  );
}
