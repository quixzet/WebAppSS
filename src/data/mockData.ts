/**
 * Мок-данные для демонстрации приложения
 * В реальном приложении заменяются данными с API
 */

import { Group, WeekSchedule } from '../types';

/** Список групп */
export const groups: Group[] = [
  { id: '1', name: 'ИСП-21-1', faculty: 'Информационные системы', course: 3 },
  { id: '2', name: 'ИСП-21-2', faculty: 'Информационные системы', course: 3 },
  { id: '3', name: 'ПР-22-1', faculty: 'Программная инженерия', course: 2 },
  { id: '4', name: 'ПР-22-2', faculty: 'Программная инженерия', course: 2 },
  { id: '5', name: 'ИС-23-1', faculty: 'Информационная безопасность', course: 1 },
  { id: '6', name: 'ИС-23-2', faculty: 'Информационная безопасность', course: 1 },
  { id: '7', name: 'МТ-21-1', faculty: 'Математика и механика', course: 3 },
  { id: '8', name: 'ЭК-22-1', faculty: 'Экономика', course: 2 },
];

/** Получить текущую дату */
function getCurrentDate(): Date {
  return new Date();
}

/** Получить дату для дня недели (0 = понедельник текущей недели) */
function getDateForDay(dayOffset: number): string {
  const now = getCurrentDate();
  const currentDay = now.getDay(); // 0 = воскресенье
  const mondayOffset = currentDay === 0 ? -6 : 1 - currentDay;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset + dayOffset);
  return monday.toISOString().split('T')[0];
}

const DAYS_OF_WEEK = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];

/** Мок-расписание для группы ИСП-21-1 */
export const mockSchedules: Record<string, WeekSchedule> = {
  '1': {
    weekNumber: 1,
    days: [
      {
        date: getDateForDay(0),
        dayOfWeek: DAYS_OF_WEEK[0],
        lessons: [
          {
            id: '1-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Базы данных',
            type: 'lecture',
            teacher: 'Иванов А.П.',
            room: '301',
            building: 'Главный корпус',
          },
          {
            id: '1-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Базы данных',
            type: 'practice',
            teacher: 'Иванов А.П.',
            room: '405',
            building: 'Главный корпус',
          },
          {
            id: '1-3',
            number: 3,
            startTime: '12:30',
            endTime: '14:00',
            subject: 'Веб-разработка',
            type: 'lab',
            teacher: 'Петров С.В.',
            room: '210',
            building: 'Корпус Б',
            isChanged: true,
          },
          {
            id: '1-4',
            number: 4,
            startTime: '14:15',
            endTime: '15:45',
            subject: 'Физическая культура',
            type: 'practice',
            teacher: 'Сидоров К.М.',
            room: 'Спортзал',
            building: 'Спорт. комплекс',
          },
        ],
      },
      {
        date: getDateForDay(1),
        dayOfWeek: DAYS_OF_WEEK[1],
        lessons: [
          {
            id: '2-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Программная инженерия',
            type: 'lecture',
            teacher: 'Козлов Д.И.',
            room: '312',
            building: 'Главный корпус',
          },
          {
            id: '2-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Операционные системы',
            type: 'lecture',
            teacher: 'Морозов Е.А.',
            room: '301',
            building: 'Главный корпус',
          },
          {
            id: '2-3',
            number: 3,
            startTime: '12:30',
            endTime: '14:00',
            subject: 'Операционные системы',
            type: 'lab',
            teacher: 'Морозов Е.А.',
            room: '215',
            building: 'Корпус Б',
          },
          {
            id: '2-4',
            number: 4,
            startTime: '14:15',
            endTime: '15:45',
            subject: 'Английский язык',
            type: 'practice',
            teacher: 'Смирнова О.Н.',
            room: '108',
            building: 'Главный корпус',
          },
        ],
      },
      {
        date: getDateForDay(2),
        dayOfWeek: DAYS_OF_WEEK[2],
        lessons: [
          {
            id: '3-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Веб-разработка',
            type: 'lecture',
            teacher: 'Петров С.В.',
            room: '305',
            building: 'Главный корпус',
          },
          {
            id: '3-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Программная инженерия',
            type: 'practice',
            teacher: 'Козлов Д.И.',
            room: '402',
            building: 'Главный корпус',
            isChanged: true,
            comment: 'Замена преподавателя',
          },
          {
            id: '3-3',
            number: 3,
            startTime: '12:30',
            endTime: '14:00',
            subject: 'Высшая математика',
            type: 'lecture',
            teacher: 'Николаев В.Г.',
            room: '301',
            building: 'Главный корпус',
          },
          {
            id: '3-4',
            number: 4,
            startTime: '14:15',
            endTime: '15:45',
            subject: 'Высшая математика',
            type: 'practice',
            teacher: 'Николаев В.Г.',
            room: '410',
            building: 'Главный корпус',
          },
          {
            id: '3-5',
            number: 5,
            startTime: '16:00',
            endTime: '17:30',
            subject: 'Базы данных',
            type: 'lab',
            teacher: 'Иванов А.П.',
            room: '210',
            building: 'Корпус Б',
          },
        ],
      },
      {
        date: getDateForDay(3),
        dayOfWeek: DAYS_OF_WEEK[3],
        lessons: [
          {
            id: '4-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Компьютерные сети',
            type: 'lecture',
            teacher: 'Волков И.С.',
            room: '303',
            building: 'Главный корпус',
          },
          {
            id: '4-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Компьютерные сети',
            type: 'lab',
            teacher: 'Волков И.С.',
            room: '218',
            building: 'Корпус Б',
          },
          {
            id: '4-3',
            number: 3,
            startTime: '12:30',
            endTime: '14:00',
            subject: 'Философия',
            type: 'lecture',
            teacher: 'Белова Т.Р.',
            room: '301',
            building: 'Главный корпус',
          },
        ],
      },
      {
        date: getDateForDay(4),
        dayOfWeek: DAYS_OF_WEEK[4],
        lessons: [
          {
            id: '5-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Веб-разработка',
            type: 'practice',
            teacher: 'Петров С.В.',
            room: '210',
            building: 'Корпус Б',
          },
          {
            id: '5-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Программная инженерия',
            type: 'lab',
            teacher: 'Козлов Д.И.',
            room: '212',
            building: 'Корпус Б',
          },
          {
            id: '5-3',
            number: 3,
            startTime: '12:30',
            endTime: '14:00',
            subject: 'Физическая культура',
            type: 'practice',
            teacher: 'Сидоров К.М.',
            room: 'Спортзал',
            building: 'Спорт. комплекс',
          },
        ],
      },
      {
        date: getDateForDay(5),
        dayOfWeek: DAYS_OF_WEEK[5],
        lessons: [
          {
            id: '6-1',
            number: 1,
            startTime: '08:30',
            endTime: '10:00',
            subject: 'Английский язык',
            type: 'practice',
            teacher: 'Смирнова О.Н.',
            room: '108',
            building: 'Главный корпус',
          },
          {
            id: '6-2',
            number: 2,
            startTime: '10:15',
            endTime: '11:45',
            subject: 'Философия',
            type: 'practice',
            teacher: 'Белова Т.Р.',
            room: '401',
            building: 'Главный корпус',
          },
        ],
      },
    ],
  },
};

// Генерируем расписания для остальных групп на основе первой
for (let i = 2; i <= 8; i++) {
  const baseSchedule = mockSchedules['1'];
  mockSchedules[String(i)] = {
    ...baseSchedule,
    days: baseSchedule.days.map(day => ({
      ...day,
      lessons: day.lessons.map(lesson => ({
        ...lesson,
        id: `${i}-${lesson.number}`,
        room: String(parseInt(lesson.room) + i * 10 || lesson.room),
      })),
    })),
  };
}

/** Статус последнего обновления */
export const mockUpdateStatus = {
  lastUpdate: new Date().toISOString(),
  nextUpdate: new Date(Date.now() + 3 * 60 * 60 * 1000).toISOString(),
  source: 'Сайт института',
  success: true,
};
