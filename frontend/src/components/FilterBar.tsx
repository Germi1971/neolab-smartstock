interface FilterOption {
  value: string;
  label: string;
}

interface FilterField {
  key: string;
  label: string;
  type: 'text' | 'select' | 'date' | 'number';
  placeholder?: string;
  options?: FilterOption[];
}

interface FilterBarProps<T> {
  filters: T;
  onFilterChange: (filters: T) => void;
  fields: FilterField[];
}

export function FilterBar<T extends Record<string, unknown>>({
  filters,
  onFilterChange,
  fields,
}: FilterBarProps<T>) {
  const handleChange = (key: string, value: unknown) => {
    onFilterChange({
      ...filters,
      [key]: value,
    });
  };

  const handleClear = () => {
    const clearedFilters = {} as T;
    onFilterChange(clearedFilters);
  };

  const hasFilters = Object.values(filters).some((v) => v !== undefined && v !== '');

  return (
    <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
      <div className="flex flex-wrap gap-4 items-end">
        {fields.map((field) => (
          <div key={field.key} className="flex-1 min-w-[150px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            {field.type === 'text' && (
              <input
                type="text"
                value={(filters[field.key] as string) || ''}
                onChange={(e) => handleChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            )}
            {field.type === 'select' && (
              <select
                value={(filters[field.key] as string) || ''}
                onChange={(e) => handleChange(field.key, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              >
                {field.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
            {field.type === 'date' && (
              <input
                type="date"
                value={(filters[field.key] as string) || ''}
                onChange={(e) => handleChange(field.key, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            )}
            {field.type === 'number' && (
              <input
                type="number"
                value={(filters[field.key] as number) || ''}
                onChange={(e) => handleChange(field.key, e.target.value ? Number(e.target.value) : '')}
                placeholder={field.placeholder}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
              />
            )}
          </div>
        ))}
        <div>
          <button
            onClick={handleClear}
            disabled={!hasFilters}
            className="px-4 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Limpiar filtros
          </button>
        </div>
      </div>
    </div>
  );
}
