import { useSKUCache } from '../hooks/useSKUCache';
import { apiClient } from '../services/apiClient';
import { SKUDetail } from '../types';

interface ModalSKUProps {
  sku: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export function ModalSKU({ sku, isOpen, onClose }: ModalSKUProps) {
  const { data, isLoading, error, refresh } = useSKUCache(sku, apiClient.getSKUDetail);

  if (!isOpen || !sku) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {isLoading ? 'Cargando...' : data?.descripcion || sku}
              </h2>
              <p className="text-sm text-gray-500 font-mono mt-1">{sku}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={refresh}
                disabled={isLoading}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
                title="Actualizar"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <button
                onClick={onClose}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}

          {data && !isLoading && (
            <div className="space-y-6">
              {/* Stock Section */}
              <section className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  Stock
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Stock Posición</p>
                    <p className="text-lg font-semibold">{data.stock.stock_posicion.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Stock Objetivo</p>
                    <p className="text-lg font-semibold">{data.stock.stock_objetivo.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Stock Seguridad</p>
                    <p className="text-lg font-semibold">{data.stock.stock_seguridad.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Punto Reorden</p>
                    <p className="text-lg font-semibold">{data.stock.punto_reorden.toLocaleString()}</p>
                  </div>
                </div>
              </section>

              {/* Purchase Suggestion Section */}
              {data.suggestion && (
                <section className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    Sugerencia de Compra
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Qty Sugerida</p>
                      <p className={`text-lg font-semibold ${data.suggestion.qty_sugerida > 0 ? 'text-green-600' : ''}`}>
                        {data.suggestion.qty_sugerida.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Qty Final</p>
                      <p className="text-lg font-semibold">
                        {data.suggestion.qty_final?.toLocaleString() || '-'}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Estado</p>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        data.suggestion.estado === 'APROBADO'
                          ? 'bg-green-100 text-green-800'
                          : data.suggestion.estado === 'RECHAZADO'
                          ? 'bg-red-100 text-red-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {data.suggestion.estado}
                      </span>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Modelo</p>
                      <p className="text-lg font-semibold">{data.suggestion.modelo_seleccionado}</p>
                    </div>
                  </div>
                  {data.suggestion.s_policy !== null && data.suggestion.S_policy !== null && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-sm text-gray-500">
                        Política (s, S): ({data.suggestion.s_policy}, {data.suggestion.S_policy})
                      </p>
                    </div>
                  )}
                </section>
              )}

              {/* ML Features Section */}
              {data.features && (
                <section className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Features ML (12m)
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Eventos</p>
                      <p className="text-lg font-semibold">{data.features.eventos_12m}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Unidades</p>
                      <p className="text-lg font-semibold">{data.features.unidades_12m.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">CV</p>
                      <p className="text-lg font-semibold">{data.features.cv_12m.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Lambda</p>
                      <p className="text-lg font-semibold">{data.features.lambda_eventos_mes_12m.toFixed(2)}</p>
                    </div>
                  </div>
                </section>
              )}

              {/* Model Info Section */}
              {data.model && (
                <section className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    Modelo Seleccionado
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-gray-500">Modelo Actual</p>
                      <p className="text-lg font-semibold">{data.model.modelo_actual}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Score</p>
                      <p className="text-lg font-semibold">{data.model.score_composite.toFixed(3)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">Drift Detectado</p>
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        data.model.drift_detected
                          ? 'bg-red-100 text-red-800'
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {data.model.drift_detected ? 'Sí' : 'No'}
                      </span>
                    </div>
                  </div>
                </section>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
