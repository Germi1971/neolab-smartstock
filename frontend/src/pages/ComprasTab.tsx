import { useState } from 'react';
import { DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { ModalSKU } from '../components/ModalSKU';
import { KPICards } from '../components/KPICards';
import { usePaginatedData } from '../hooks/usePaginatedData';
import { useDebounce } from '../hooks/useDebounce';
import { apiClient } from '../services/apiClient';
import { PurchaseSuggestion, PurchaseFilters, ApiListResponse } from '../types';

const columns = [
  { key: 'sku', header: 'SKU', sortable: true, width: '120px' },
  { key: 'descripcion', header: 'Descripción', sortable: true, width: '250px' },
  { key: 'stock_posicion', header: 'Stock Pos.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'stock_objetivo', header: 'Stock Obj (Param)', sortable: true, width: '120px', align: 'right' as const },
  { key: 'stock_objetivo_calculado', header: 'Stock Obj (ML)', sortable: true, width: '120px', align: 'right' as const },
  { key: 'qty_sugerida', header: 'Qty Sug.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'estado', header: 'Estado', sortable: true, width: '120px' },
  { key: 'modelo_seleccionado', header: 'Modelo', sortable: true, width: '100px' },
  { key: 'updated_at', header: 'Actualizado', sortable: true, width: '150px' },
];

export function ComprasTab() {
  const [selectedSKU, setSelectedSKU] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [filters, setFilters] = useState<PurchaseFilters>({});
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
  } = usePaginatedData<ApiListResponse<PurchaseSuggestion>, PurchaseFilters>({
    fetchFn: (params) => apiClient.getPurchaseSuggestions(params),
    filters: debouncedFilters,
    initialPageSize: 25,
  });

  const suggestions = data?.items || [];
  const stats = data?.stats;

  const handleApprove = async (sku: string, qty: number, notas: string) => {
    try {
      await apiClient.approveSuggestion(sku, { qty_final: qty, notas });
      refresh();
    } catch (err) {
      console.error('Error approving suggestion:', err);
      alert('Error al aprobar la sugerencia');
    }
  };

  const handleUnapprove = async (sku: string) => {
    if (!confirm('¿Está seguro de volver esta sugerencia a automático?')) return;
    try {
      await apiClient.unapproveSuggestion(sku);
      refresh();
    } catch (err) {
      console.error('Error unapproving suggestion:', err);
      alert('Error al revertir la aprobación');
    }
  };

  const handleExport = async () => {
    try {
      const blob = await apiClient.exportPurchaseOrder({
        ...debouncedFilters,
        limit: 10000,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `purchase_order_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting:', err);
      alert('Error al exportar la orden de compra');
    }
  };

  const handleRowClick = (row: PurchaseSuggestion) => {
    setSelectedSKU(row.sku);
    setIsModalOpen(true);
  };

  const kpiData = stats
    ? [
      {
        title: 'Total Sugerencias',
        value: stats.total_sugerencias?.toString() || '0',
        color: 'blue' as const,
      },
      {
        title: 'Pendientes',
        value: stats.pendientes?.toString() || '0',
        color: 'yellow' as const,
      },
      {
        title: 'Aprobadas',
        value: stats.aprobadas?.toString() || '0',
        color: 'green' as const,
      },
      {
        title: 'Qty Total Sugerida',
        value: stats.total_qty_sugerida?.toLocaleString() || '0',
        color: 'purple' as const,
      },
    ]
    : [];

  const filterFields = [
    { key: 'sku', label: 'SKU', type: 'text' as const, placeholder: 'Buscar SKU...' },
    { key: 'descripcion', label: 'Descripción', type: 'text' as const, placeholder: 'Buscar descripción...' },
    {
      key: 'estado',
      label: 'Estado',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'PENDIENTE', label: 'Pendiente' },
        { value: 'APROBADO', label: 'Aprobado' },
        { value: 'RECHAZADO', label: 'Rechazado' },
      ],
    },
    {
      key: 'modelo',
      label: 'Modelo',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'SIN_DATOS', label: 'Sin Datos' },
        { value: 'REGULAR', label: 'Regular' },
        { value: 'CROSTON', label: 'Croston' },
        { value: 'SBA', label: 'SBA' },
        { value: 'TSB', label: 'TSB' },
        { value: 'MONTE_CARLO', label: 'Monte Carlo' },
      ],
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Gestión de Compras</h2>
        <div className="flex gap-2">
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
            title="Descargar CSV con reporte completo de todos los SKU"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Descargar reporte completo (CSV)
          </button>
        </div>
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
        data={suggestions}
        sortConfig={sortConfig}
        onSort={handleSort}
        onRowClick={handleRowClick}
        isLoading={isLoading}
        rowActions={(row) => (
          <div className="flex gap-2">
            {row.estado === 'PENDIENTE' && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  const qty = prompt('Ingrese cantidad final:', row.qty_sugerida.toString());
                  if (qty !== null) {
                    const notas = prompt('Notas (opcional):') || '';
                    handleApprove(row.sku, parseInt(qty, 10), notas);
                  }
                }}
                className="px-2 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
              >
                Aprobar
              </button>
            )}
            {row.estado === 'APROBADO' && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleUnapprove(row.sku);
                }}
                className="px-2 py-1 bg-yellow-600 text-white text-xs rounded hover:bg-yellow-700"
              >
                Revertir
              </button>
            )}
          </div>
        )}
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
