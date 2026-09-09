import { useState, useRef, useEffect } from 'react';
import { Group } from '../types';
import { groups } from '../data/mockData';

interface GroupSelectorProps {
  selectedGroup: string | null;
  onSelect: (groupId: string) => void;
}

/**
 * Компонент выбора группы с поиском
 */
export function GroupSelector({ selectedGroup, onSelect }: GroupSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const filteredGroups = groups.filter(g =>
    g.name.toLowerCase().includes(search.toLowerCase()) ||
    g.faculty.toLowerCase().includes(search.toLowerCase())
  );

  const selectedGroupData = groups.find(g => g.id === selectedGroup);

  // Закрытие при клике вне
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="px-4 py-3" ref={dropdownRef}>
      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-4 py-3 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md transition-all duration-200 active:scale-[0.98]"
        >
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center">
              <svg className="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div className="text-left">
              {selectedGroupData ? (
                <>
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">
                    {selectedGroupData.name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {selectedGroupData.faculty} • {selectedGroupData.course} курс
                  </p>
                </>
              ) : (
                <p className="text-gray-400 dark:text-gray-500 text-sm">
                  Выберите группу
                </p>
              )}
            </div>
          </div>
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {/* Dropdown */}
        {isOpen && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200">
            {/* Поиск */}
            <div className="p-3 border-b border-gray-100 dark:border-gray-700">
              <div className="relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Поиск группы..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-700 border-0 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>
            </div>

            {/* Список групп */}
            <div className="max-h-64 overflow-y-auto">
              {filteredGroups.length > 0 ? (
                filteredGroups.map(group => (
                  <button
                    key={group.id}
                    onClick={() => {
                      onSelect(group.id);
                      setIsOpen(false);
                      setSearch('');
                    }}
                    className={`w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left ${
                      group.id === selectedGroup ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full ${
                      group.id === selectedGroup ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
                    }`} />
                    <div>
                      <p className="font-medium text-sm text-gray-900 dark:text-white">
                        {group.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {group.faculty} • {group.course} курс
                      </p>
                    </div>
                  </button>
                ))
              ) : (
                <div className="px-4 py-8 text-center text-gray-400 text-sm">
                  Группы не найдены
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
