import { useState, useEffect } from 'react';
import { DataTable } from '../components/DataTable';
import { FilterBar } from '../components/FilterBar';
import { Pagination } from '../components/Pagination';
import { KPICards } from '../components/KPICards';
import { usePaginatedData } from '../hooks/usePaginatedData';
import { useDebounce } from '../hooks/useDebounce';
import { apiClient } from '../services/apiClient';
import { MLRun, MLRunFilters, ApiListResponse, MLModelInfo } from '../types';

const runColumns = [
  { key: 'run_id', header: 'Run ID', sortable: true, width: '200px' },
  { key: 'started_at', header: 'Inicio', sortable: true, width: '150px' },
  { key: 'finished_at', header: 'Fin', sortable: true, width: '150px' },
  { key: 'skus_procesados', header: 'SKUs Proc.', sortable: true, width: '100px', align: 'right' as const },
  { key: 'skus_exitosos', header: 'Exitosos', sortable: true, width: '100px', align: 'right' as const },
  { key: 'skus_fallidos', header: 'Fallidos', sortable: true, width: '100px', align: 'right' as const },
  { key: 'duracion_segundos', header: 'Duración (s)', sortable: true, width: '120px', align: 'right' as const },
  { key: 'triggered_by', header: 'Trigger', sortable: true, width: '100px' },
];

const modelColumns = [
  { key: 'sku', header: 'SKU', sortable: true, width: '120px' },
  { key: 'modelo_actual', header: 'Modelo Actual', sortable: true, width: '120px' },
  { key: 'modelo_anterior', header: 'Modelo Ant.', sortable: true, width: '120px' },
  { key: 'fecha_seleccion', header: 'Fecha Sel.', sortable: true, width: '150px' },
  { key: 'score_composite', header: 'Score', sortable: true, width: '80px', align: 'right' as const },
  { key: 'cv_12m', header: 'CV 12m', sortable: true, width: '80px', align: 'right' as const },
  { key: 'lambda_eventos_mes_12m', header: 'Lambda', sortable: true, width: '80px', align: 'right' as const },
  { key: 'drift_detected', header: 'Drift', sortable: true, width: '80px' },
];

export function MLTab() {
  const [activeSubTab, setActiveSubTab] = useState<'runs' | 'models' | 'features'>('runs');
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [filters, setFilters] = useState<MLRunFilters>({});
  const debouncedFilters = useDebounce(filters, 300);
  const [isRunningML, setIsRunningML] = useState(false);
  const [runProgress, setRunProgress] = useState<string>('');
  const [models, setModels] = useState<MLModelInfo[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const {
    data: runsData,
    pagination,
    sortConfig,
    isLoading,
    error,
    handlePageChange,
    handlePageSizeChange,
    handleSort,
    refresh,
  } = usePaginatedData<ApiListResponse<MLRun>, MLRunFilters>({
    fetchFn: (params) => apiClient.getMLRuns(params),
    filters: debouncedFilters,
    initialPageSize: 10,
  });

  const runs = runsData?.items || [];

  useEffect(() => {
    if (activeSubTab === 'models') {
      loadModels();
    }
  }, [activeSubTab]);

  const loadModels = async () => {
    setIsLoadingModels(true);
    try {
      const data = await apiClient.getMLModels({ limit: 100 });
      setModels(data.items || []);
    } catch (err) {
      console.error('Error loading models:', err);
    } finally {
      setIsLoadingModels(false);
    }
  };

  const handleRunML = async () => {
    if (!confirm('¿Está seguro de ejecutar el pipeline ML completo? Esto puede tardar varios minutos.')) {
      return;
    }
    setIsRunningML(true);
    setRunProgress('Iniciando pipeline ML...');
    try {
      const result = await apiClient.runMLPipeline();
      setRunProgress(`Pipeline completado. Run ID: ${result.run_id}`);
      refresh();
    } catch (err) {
      console.error('Error running ML pipeline:', err);
      setRunProgress('Error al ejecutar el pipeline');
    } finally {
      setIsRunningML(false);
    }
  };

  const handleRowClick = (row: MLRun) => {
    setSelectedRun(row.run_id);
  };

  const kpiData = runsData?.stats
    ? [
        {
          title: 'Total Runs',
          value: runsData.stats.total_runs?.toString() || '0',
          color: 'blue' as const,
        },
        {
          title: 'Runs Exitosos',
          value: runsData.stats.exitosos?.toString() || '0',
          color: 'green' as const,
        },
        {
          title: 'Runs Fallidos',
          value: runsData.stats.fallidos?.toString() || '0',
          color: 'red' as const,
        },
        {
          title: 'SKUs Procesados (último)',
          value: runs[0]?.skus_procesados?.toString() || '0',
          color: 'purple' as const,
        },
      ]
    : [];

  const filterFields = [
    {
      key: 'status',
      label: 'Estado',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'SUCCESS', label: 'Exitoso' },
        { value: 'PARTIAL', label: 'Parcial' },
        { value: 'FAILED', label: 'Fallido' },
      ],
    },
    {
      key: 'triggered_by',
      label: 'Trigger',
      type: 'select' as const,
      options: [
        { value: '', label: 'Todos' },
        { value: 'SCHEDULER', label: 'Scheduler' },
        { value: 'MANUAL', label: 'Manual' },
        { value: 'API', label: 'API' },
      ],
    },
    { key: 'fecha_desde', label: 'Desde', type: 'date' as const },
    { key: 'fecha_hasta', label: 'Hasta', type: 'date' as const },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Machine Learning</h2>
        <button
          onClick={handleRunML}
          disabled={isRunningML}
          className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${
            isRunningML
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 text-white'
          }`}
        >
          {isRunningML ? (
            <>
              <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Ejecutando...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Ejecutar Pipeline ML
            </>
          )}
        </button>
      </div>

      {runProgress && (
        <div className={`px-4 py-2 rounded-lg ${runProgress.includes('Error') ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
          {runProgress}
        </div>
      )}

      <KPICards cards={kpiData} isLoading={isLoading} />

      {/* Sub-tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {[
            { key: 'runs', label: 'Ejecuciones' },
            { key: 'models', label: 'Modelos por SKU' },
            { key: 'features', label: 'Features' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveSubTab(tab.key as typeof activeSubTab)}
              className={`py-2 px-4 font-medium text-sm border-b-2 transition-colors ${
                activeSubTab === tab.key
                  ? 'border-purple-600 text-purple-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeSubTab === 'runs' && (
        <>
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
            columns={runColumns}
            data={runs}
            sortConfig={sortConfig}
            onSort={handleSort}
            onRowClick={handleRowClick}
            isLoading={isLoading}
            rowClassName={(row) =>
              row.skus_fallidos > 0 ? 'bg-red-50' : row.skus_exitosos === row.skus_procesados ? 'bg-green-50' : ''
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
        </>
      )}

      {activeSubTab === 'models' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900">Modelos Seleccionados por SKU</h3>
            <button
              onClick={loadModels}
              className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
            >
              Actualizar
            </button>
          </div>
          <DataTable
            columns={modelColumns}
            data={models}
            isLoading={isLoadingModels}
            rowClassName={(row) =>
              row.drift_detected ? 'bg-yellow-50' : ''
            }
          />
        </div>
      )}

      {activeSubTab === 'features' && (
        <div className="p-8 text-center text-gray-500">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-lg font-medium">Features por SKU</p>
          <p className="text-sm mt-2">Seleccione un SKU en la pestaña "Stock" para ver sus features detallados.</p>
        </div>
      )}

      {/* Run Detail Modal */}
      {selectedRun && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-semibold text-gray-900">
                  Detalle de Ejecución
                </h3>
                <button
                  onClick={() => setSelectedRun(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-sm text-gray-500">Run ID</p>
                    <p className="font-mono text-sm">{selectedRun}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-sm text-gray-500">Estado</p>
                    <p className="font-medium">
                      {runs.find(r => r.run_id === selectedRun)?.skus_fallidos === 0 ? (
                        <span className="text-green-600">Exitoso</span>
                      ) : runs.find(r => r.run_id === selectedRun)?.skus_exitosos === 0 ? (
                        <span className="text-red-600">Fallido</span>
                      ) : (
                        <span className="text-yellow-600">Parcial</span>
                      )}
                    </p>
                  </div>
                </div>

                {runs.find(r => r.run_id === selectedRun)?.error_log && (
                  <div className="bg-red-50 p-4 rounded-lg">
                    <p className="text-sm font-medium text-red-700 mb-2">Errores:</p>
                    <pre className="text-xs text-red-600 overflow-x-auto">
                      {JSON.stringify(runs.find(r => r.run_id === selectedRun)?.error_log, null, 2)}
                    </pre>
                  </div>
                )}

                <div className="flex justify-end">
                  <button
                    onClick={() => setSelectedRun(null)}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                  >
                    Cerrar
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
