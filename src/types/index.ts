/**
 * Типы данных для приложения расписания
 * Совместимы с API эндпоинтами бэкенда
 */

/** Тип занятия */
export type LessonType = 'lecture' | 'practice' | 'lab' | 'exam' | 'consultation';

/** Данные о занятии */
export interface Lesson {
  id: string;
  /** Номер пары (1-6) */
  number: number;
  /** Время начала */
  startTime: string;
  /** Время окончания */
  endTime: string;
  /** Название предмета */
  subject: string;
  /** Тип занятия */
  type: LessonType;
  /** Преподаватель */
  teacher: string;
  /** Аудитория */
  room: string;
  /** Корпус */
  building?: string;
  /** Была ли изменена */
  isChanged?: boolean;
  /** Комментарий */
  comment?: string;
}

/** Расписание на один день */
export interface DaySchedule {
  /** Дата в формате YYYY-MM-DD */
  date: string;
  /** День недели */
  dayOfWeek: string;
  /** Занятия */
  lessons: Lesson[];
}

/** Расписание на неделю */
export interface WeekSchedule {
  /** Номер недели */
  weekNumber: number;
  /** Дни */
  days: DaySchedule[];
}

/** Группа */
export interface Group {
  id: string;
  name: string;
  faculty: string;
  course: number;
}

/** Статус обновления */
export interface UpdateStatus {
  lastUpdate: string;
  nextUpdate: string;
  source: string;
  success: boolean;
}

/** Режим отображения */
export type ViewMode = 'day' | 'week';

/** Цветовая схема для типов занятий */
export const LESSON_COLORS: Record<LessonType, { bg: string; border: string; text: string; darkBg: string; darkBorder: string }> = {
  lecture: {
    bg: 'bg-blue-50',
    border: 'border-blue-400',
    text: 'text-blue-700',
    darkBg: 'dark:bg-blue-900/30',
    darkBorder: 'dark:border-blue-500',
  },
  practice: {
    bg: 'bg-green-50',
    border: 'border-green-400',
    text: 'text-green-700',
    darkBg: 'dark:bg-green-900/30',
    darkBorder: 'dark:border-green-500',
  },
  lab: {
    bg: 'bg-purple-50',
    border: 'border-purple-400',
    text: 'text-purple-700',
    darkBg: 'dark:bg-purple-900/30',
    darkBorder: 'dark:border-purple-500',
  },
  exam: {
    bg: 'bg-red-50',
    border: 'border-red-400',
    text: 'text-red-700',
    darkBg: 'dark:bg-red-900/30',
    darkBorder: 'dark:border-red-500',
  },
  consultation: {
    bg: 'bg-amber-50',
    border: 'border-amber-400',
    text: 'text-amber-700',
    darkBg: 'dark:bg-amber-900/30',
    darkBorder: 'dark:border-amber-500',
  },
};

/** Названия типов занятий */
export const LESSON_TYPE_LABELS: Record<LessonType, string> = {
  lecture: 'Лекция',
  practice: 'Практика',
  lab: 'Лабораторная',
  exam: 'Экзамен',
  consultation: 'Консультация',
};
