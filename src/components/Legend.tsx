/**
 * Легенда типов занятий
 */
export function Legend() {
  const types = [
    { label: 'Лекция', color: 'bg-blue-400' },
    { label: 'Практика', color: 'bg-green-400' },
    { label: 'Лаб.', color: 'bg-purple-400' },
    { label: 'Экзамен', color: 'bg-red-400' },
    { label: 'Конс.', color: 'bg-amber-400' },
  ];

  return (
    <div className="flex items-center justify-center gap-3 flex-wrap py-2">
      {types.map(type => (
        <div key={type.label} className="flex items-center gap-1.5">
          <div className={`w-2.5 h-2.5 rounded-sm ${type.color}`} />
          <span className="text-[11px] text-gray-500 dark:text-gray-400">{type.label}</span>
        </div>
      ))}
    </div>
  );
}
