interface KPICard {
  title: string;
  value: string;
  subtitle?: string;
  color: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
}

interface KPICardsProps {
  cards: KPICard[];
  isLoading?: boolean;
}

const colorClasses: Record<string, { bg: string; text: string }> = {
  blue: { bg: 'bg-blue-50', text: 'text-blue-600' },
  green: { bg: 'bg-green-50', text: 'text-green-600' },
  yellow: { bg: 'bg-yellow-50', text: 'text-yellow-600' },
  red: { bg: 'bg-red-50', text: 'text-red-600' },
  purple: { bg: 'bg-purple-50', text: 'text-purple-600' },
};

export function KPICards({ cards, isLoading = false }: KPICardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-gray-50 rounded-lg p-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/2 mb-2" />
            <div className="h-8 bg-gray-200 rounded w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (cards.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => {
        const colors = colorClasses[card.color];
        return (
          <div
            key={index}
            className={`${colors.bg} rounded-lg p-4 border border-gray-100`}
          >
            <p className="text-sm font-medium text-gray-600">{card.title}</p>
            <p className={`text-2xl font-bold ${colors.text} mt-1`}>
              {card.value}
            </p>
            {card.subtitle && (
              <p className="text-xs text-gray-500 mt-1">{card.subtitle}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
