import { useState } from 'react';
import { DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { ModalSKU } from '../components/ModalSKU';
import { KPICards } from '../components/KPICards';
import { usePaginatedData } from '../hooks/usePaginatedData';
import { useDebounce } from '../hooks/useDebounce';
import { apiClient } from '../services/apiClient';
import { StockItem, StockFilters, ApiListResponse } from '../types';

const columns = [
  { key: 'sku', header: 'SKU', sortable: true, width: '120px' },
  { key: 'descripcion', header: 'Descripción', sortable: true, width: '300px' },
  { key: 'stock_posicion', header: 'Stock Pos.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'stock_objetivo', header: 'Stock Obj.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'stock_seguridad', header: 'Stock Seg.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'punto_reorden', header: 'Pto. Reorden', sortable: true, width: '100px', align: 'right' as const },
  { key: 'moq', header: 'MOQ', sortable: true, width: '80px', align: 'right' as const },
  { key: 'activo', header: 'Activo', sortable: true, width: '80px' },
  { key: 'updated_at', header: 'Actualizado', sortable: true, width: '150px' },
];

export function StockTab() {
  const [selectedSKU, setSelectedSKU] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [filters, setFilters] = useState<StockFilters>({});
  const debouncedFilters = useDebounce(filters, 300);

  const {
    data,
    pagination,
    sortConfig,
    isLoading,
    error,
    handlePageChange,
    handlePageSizeChange,
    handleSort,
    refresh,
  } = usePaginatedData<ApiListResponse<StockItem>, StockFilters>({
    fetchFn: (params) => apiClient.getStock(params),
    filters: debouncedFilters,
    initialPageSize: 25,
  });

  const stock = data?.items || [];
  const stats = data?.stats;

  const handleRowClick = (row: StockItem) => {
    setSelectedSKU(row.sku);
    setIsModalOpen(true);
  };

  const kpiData = stats
    ? [
        {
          title: 'Total SKUs',
          value: stats.total_skus?.toString() || '0',
          color: 'blue' as const,
        },
        {
          title: 'Activos',
          value: stats.activos?.toString() || '0',
          color: 'green' as const,
        },
        {
          title: 'Stock Bajo',
          value: stats.stock_bajo?.toString() || '0',
          color: 'red' as const,
        },
        {
          title: 'Con MOQ',
          value: stats.con_moq?.toString() || '0',
          color: 'purple' as const,
        },
      ]
    : [];

  const filterFields = [
    { key: 'sku', label: 'SKU', type: 'text' as const, placeholder: 'Buscar SKU...' },
    { key: 'descripcion', label: 'Descripción', type: 'text' as const, placeholder: 'Buscar descripción...' },
    {
      key: 'activo',
      label: 'Estado',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'true', label: 'Activo' },
        { value: 'false', label: 'Inactivo' },
      ],
    },
    {
      key: 'stock_bajo',
      label: 'Stock Bajo',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'true', label: 'Sí' },
        { value: 'false', label: 'No' },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Stock</h2>
        <button
          onClick={refresh}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Actualizar
        </button>
      </div>

      <KPICards cards={kpiData} isLoading={isLoading} />

      <FilterBar
        filters={filters}
        onFilterChange={setFilters}
        fields={filterFields}
      />

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <DataTable
        columns={columns}
        data={stock}
        sortConfig={sortConfig}
        onSort={handleSort}
        onRowClick={handleRowClick}
        isLoading={isLoading}
        rowClassName={(row) =>
          row.stock_posicion < row.stock_seguridad ? 'bg-red-50' : ''
        }
      />

      <Pagination
        currentPage={pagination.page}
        pageSize={pagination.pageSize}
        totalItems={pagination.totalItems}
        totalPages={pagination.totalPages}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
      />

      <ModalSKU
        sku={selectedSKU}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedSKU(null);
        }}
      />
    </div>
  );
}
