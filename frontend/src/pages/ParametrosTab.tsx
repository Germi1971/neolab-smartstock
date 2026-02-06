import { useState } from 'react';
import { DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { ModalSKU } from '../components/ModalSKU';
import { KPICards } from '../components/KPICards';
import { usePaginatedData } from '../hooks/usePaginatedData';
import { useDebounce } from '../hooks/useDebounce';
import { apiClient } from '../services/apiClient';
import { SKUParameter, ParameterFilters, ApiListResponse } from '../types';

const columns = [
  { key: 'sku', header: 'SKU', sortable: true, width: '120px' },
  { key: 'descripcion', header: 'Descripción', sortable: true, width: '250px' },
  { key: 'stock_objetivo', header: 'Stock Objetivo', sortable: true, width: '120px', align: 'right' as const },
  { key: 'stock_seguridad', header: 'Stock Seg.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'punto_reorden', header: 'Pto. Reorden', sortable: true, width: '100px', align: 'right' as const },
  { key: 'moq', header: 'MOQ', sortable: true, width: '80px', align: 'right' as const },
  { key: 'multiplo', header: 'Múltiplo', sortable: true, width: '80px', align: 'right' as const },
  { key: 'activo', header: 'Activo', sortable: true, width: '80px' },
  { key: 'updated_at', header: 'Actualizado', sortable: true, width: '150px' },
];

export function ParametrosTab() {
  const [selectedSKU, setSelectedSKU] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingSKU, setEditingSKU] = useState<SKUParameter | null>(null);
  const [filters, setFilters] = useState<ParameterFilters>({});
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
  } = usePaginatedData<ApiListResponse<SKUParameter>, ParameterFilters>({
    fetchFn: (params) => apiClient.getSKUParameters(params),
    filters: debouncedFilters,
    initialPageSize: 25,
  });

  const parameters = data?.items || [];
  const stats = data?.stats;

  const handleSave = async (sku: string, updates: Partial<SKUParameter>) => {
    try {
      await apiClient.updateSKUParameter(sku, updates);
      refresh();
      setIsEditModalOpen(false);
      setEditingSKU(null);
    } catch (err) {
      console.error('Error updating parameter:', err);
      alert('Error al actualizar el parámetro');
    }
  };

  const handleRowClick = (row: SKUParameter) => {
    setSelectedSKU(row.sku);
    setIsModalOpen(true);
  };

  const handleEdit = (row: SKUParameter, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSKU(row);
    setIsEditModalOpen(true);
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
          title: 'Inactivos',
          value: stats.inactivos?.toString() || '0',
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
      key: 'tiene_moq',
      label: 'Tiene MOQ',
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
        <h2 className="text-2xl font-bold text-gray-900">Parámetros por SKU</h2>
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
        data={parameters}
        sortConfig={sortConfig}
        onSort={handleSort}
        onRowClick={handleRowClick}
        isLoading={isLoading}
        rowActions={(row) => (
          <button
            onClick={(e) => handleEdit(row, e)}
            className="px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
          >
            Editar
          </button>
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

      {/* Edit Modal */}
      {isEditModalOpen && editingSKU && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-semibold text-gray-900">
                  Editar Parámetros: {editingSKU.sku}
                </h3>
                <button
                  onClick={() => {
                    setIsEditModalOpen(false);
                    setEditingSKU(null);
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  handleSave(editingSKU.sku, {
                    stock_objetivo: parseInt(formData.get('stock_objetivo') as string, 10),
                    stock_seguridad: parseInt(formData.get('stock_seguridad') as string, 10),
                    punto_reorden: parseInt(formData.get('punto_reorden') as string, 10),
                    moq: parseInt(formData.get('moq') as string, 10) || null,
                    multiplo: parseInt(formData.get('multiplo') as string, 10) || null,
                    activo: formData.get('activo') === 'true',
                  });
                }}
                className="space-y-4"
              >
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Stock Objetivo
                    </label>
                    <input
                      type="number"
                      name="stock_objetivo"
                      defaultValue={editingSKU.stock_objetivo}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Stock Seguridad
                    </label>
                    <input
                      type="number"
                      name="stock_seguridad"
                      defaultValue={editingSKU.stock_seguridad}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Punto de Reorden
                    </label>
                    <input
                      type="number"
                      name="punto_reorden"
                      defaultValue={editingSKU.punto_reorden}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      MOQ
                    </label>
                    <input
                      type="number"
                      name="moq"
                      defaultValue={editingSKU.moq || ''}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Múltiplo
                    </label>
                    <input
                      type="number"
                      name="multiplo"
                      defaultValue={editingSKU.multiplo || ''}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Activo
                    </label>
                    <select
                      name="activo"
                      defaultValue={editingSKU.activo.toString()}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="true">Sí</option>
                      <option value="false">No</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsEditModalOpen(false);
                      setEditingSKU(null);
                    }}
                    className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Guardar
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
