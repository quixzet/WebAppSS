import { useState } from 'react';
import { Header } from './components/Header';
import { GroupSelector } from './components/GroupSelector';
import { ViewToggle } from './components/ViewToggle';
import { DayView } from './components/DayView';
import { WeekView } from './components/WeekView';
import { DayNavigation } from './components/DayNavigation';
import { Legend } from './components/Legend';
import { LoadingSpinner } from './components/LoadingSpinner';
import { EmptyState } from './components/EmptyState';
import { useSchedule } from './hooks/useSchedule';

/**
 * Главный компонент приложения расписания
 * Адаптирован для интеграции в Telegram WebApp
 * 
 * Функционал:
 * - Выбор группы из списка с поиском
 * - Отображение расписания на день/неделю
 * - Переключение между видами
 * - Темная/светлая тема
 * - Цветовая кодировка типов пар
 * - Индикатор текущей пары
 * - Индикация изменений в расписании
 */
function App() {
  const [selectedGroup, setSelectedGroup] = useState<string | null>('1');
  const {
    schedule,
    currentDay,
    currentLessonIndex,
    isToday,
    loading,
    viewMode,
    setViewMode,
    selectedDayIndex,
    setSelectedDayIndex,
    lastUpdate,
  } = useSchedule(selectedGroup);

  const handleGroupSelect = (groupId: string) => {
    setSelectedGroup(groupId);
  };

  const handlePreviousDay = () => {
    if (selectedDayIndex > 0) {
      setSelectedDayIndex(selectedDayIndex - 1);
    }
  };

  const handleNextDay = () => {
    if (schedule && selectedDayIndex < schedule.days.length - 1) {
      setSelectedDayIndex(selectedDayIndex + 1);
    }
  };

  const handleGoToToday = () => {
    if (schedule) {
      const today = new Date().toISOString().split('T')[0];
      const todayIndex = schedule.days.findIndex(d => d.date === today);
      if (todayIndex >= 0) {
        setSelectedDayIndex(todayIndex);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-300">
      {/* Шапка */}
      <Header lastUpdate={lastUpdate} />

      <main className="max-w-lg mx-auto pb-8">
        {/* Выбор группы */}
        <GroupSelector selectedGroup={selectedGroup} onSelect={handleGroupSelect} />

        {/* Основной контент */}
        {selectedGroup ? (
          <div className="px-4 space-y-4">
            {/* Переключатель вида */}
            <div className="flex items-center justify-between">
              <ViewToggle viewMode={viewMode} onChange={setViewMode} />
            </div>

            {/* Легенда */}
            <Legend />

            {/* Загрузка */}
            {loading && <LoadingSpinner />}

            {/* Расписание - вид "День" */}
            {!loading && schedule && viewMode === 'day' && currentDay && (
              <div className="space-y-4">
                <DayNavigation
                  currentDayIndex={selectedDayIndex}
                  totalDays={schedule.days.length}
                  onPrevious={handlePreviousDay}
                  onNext={handleNextDay}
                  onToday={handleGoToToday}
                  isToday={isToday}
                />
                <DayView
                  day={currentDay}
                  currentLessonIndex={currentLessonIndex}
                  isToday={isToday}
                />
              </div>
            )}

            {/* Расписание - вид "Неделя" */}
            {!loading && schedule && viewMode === 'week' && (
              <WeekView
                schedule={schedule}
                selectedDayIndex={selectedDayIndex}
                onSelectDay={setSelectedDayIndex}
                currentLessonIndex={currentLessonIndex}
              />
            )}

            {/* Расписание не найдено */}
            {!loading && !schedule && (
              <EmptyState type="no-schedule" />
            )}
          </div>
        ) : (
          <EmptyState type="no-group" />
        )}

        {/* Информация об обновлении */}
        {selectedGroup && lastUpdate && (
          <div className="px-4 mt-8">
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-800/50 rounded-xl py-3 px-4">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>Автообновление каждые 3 часа</span>
            </div>
          </div>
        )}

        {/* Футер */}
        <footer className="px-4 mt-6 text-center">
          <p className="text-[11px] text-gray-300 dark:text-gray-700">
            Расписание занятий • Telegram WebApp
          </p>
        </footer>
      </main>
    </div>
  );
}

export default App;
