import { useSKUCache } from '../hooks/useSKUCache';
import { apiClient } from '../services/apiClient';

interface ModalSKUProps {
  sku: string | null;
  isOpen: boolean;
  onClose: () => void;
}

/**
 * Shape real del endpoint /ml/sku/{sku}
 */
type MLFeature = Record<string, any>;

type EventoRaw = Record<string, any>;

type MLDetailResponse = {
  sku: string;
  features?: MLFeature | null;
  eventos?: EventoRaw[] | null;
};

function n(v: any, fallback = 0): number {
  const num = Number(v);
  return Number.isFinite(num) ? num : fallback;
}

function fmtNum(v: any, digits = 0): string {
  const num = Number(v);
  if (!Number.isFinite(num)) return '-';
  return num.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function fmtUSD(v: any): string {
  const num = Number(v);
  if (!Number.isFinite(num)) return '-';
  return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(v: any): string {
  if (!v) return '-';
  // v viene como "YYYY-MM-DD" o ISO
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toISOString().slice(0, 10);
}

function getEv(ev: EventoRaw, key: string) {
  // soporta claves mayúsculas del backend y variantes posibles
  const direct = ev?.[key];
  if (direct !== undefined) return direct;

  const alt = ev?.[key.toLowerCase()];
  if (alt !== undefined) return alt;

  // mapeos comunes
  const map: Record<string, string[]> = {
    Fecha: ['fecha', 'date', 'Fecha'],
    FAC: ['fac', 'Factura', 'Comprobante', 'FAC'],
    Qty: ['qty', 'cantidad', 'Qty'],
    ClienteNombre: ['clienteNombre', 'cliente_nombre', 'ClienteNombre'],
    ClienteN: ['clienteN', 'cliente_n', 'ClienteN'],
    UnitPrice_USD: ['unitPriceUsd', 'unit_price_usd', 'UnitPrice_USD'],
    UnitCost_USD: ['unitCostUsd', 'unit_cost_usd', 'UnitCost_USD'],
    Revenue_USD: ['revenueUsd', 'Revenue_USD'],
    Margin_USD: ['marginUsd', 'Margin_USD'],
    SKU: ['sku', 'SKU'],
  };

  const keys = map[key] || [];
  for (const k of keys) {
    if (ev?.[k] !== undefined) return ev[k];
  }

  return undefined;
}

export function ModalSKU({ sku, isOpen, onClose }: ModalSKUProps) {
  const { data, isLoading, error, refresh } = useSKUCache<MLDetailResponse>(
    sku,
    (s) => apiClient.getSKUDetail(s) as Promise<MLDetailResponse>
  );

  if (!isOpen || !sku) return null;

  const features = data?.features || null;
  const eventos = Array.isArray(data?.eventos) ? data!.eventos! : [];

  const titulo = (features?.producto as string) || (features?.descripcion as string) || sku;

  // KPIs rápidos desde features
  const tipoDemanda = features?.tipo_demanda ?? '-';
  const leadTime = features?.lead_time_dias ?? '-';
  const stockMin = features?.stock_min ?? '-';
  const stockObj = features?.stock_objetivo ?? '-';
  const moq = features?.moq ?? '-';
  const multiplo = features?.multiplo_compra ?? '-';
  const z = features?.z_servicio ?? '-';
  const activo = features?.activo ?? '-';

  // 12m
  const mesesObs = features?.meses_obs_12m ?? '-';
  const mesesConVenta = features?.meses_con_venta_12m ?? '-';
  const demandaMensual = features?.demanda_prom_mensual_12m ?? null;
  const sigmaMensual = features?.sigma_mensual_12m ?? null;
  const eventos12m = features?.eventos_12m ?? '-';
  const qEvento = features?.q_evento_12m ?? null;
  const margenTotal = features?.margen_total_12m ?? null;
  const revenueProm = features?.revenue_prom_evento_12m ?? null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {isLoading ? 'Cargando...' : titulo}
              </h2>
              <p className="text-sm text-gray-500 font-mono mt-1">{sku}</p>

              {features?.marca || features?.category || features?.sub_category ? (
                <p className="text-sm text-gray-600 mt-1">
                  {[features?.marca, features?.category, features?.sub_category].filter(Boolean).join(' · ')}
                </p>
              ) : null}
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
                title="Cerrar"
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

          {!isLoading && data && (
            <div className="space-y-6">
              {/* Parámetros / Reposición */}
              <section className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  Parámetros
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Tipo Demanda</p>
                    <p className="text-lg font-semibold">{String(tipoDemanda)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Lead Time (días)</p>
                    <p className="text-lg font-semibold">{String(leadTime)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Stock Min</p>
                    <p className="text-lg font-semibold">{String(stockMin)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Stock Objetivo</p>
                    <p className="text-lg font-semibold">{String(stockObj)}</p>
                  </div>

                  <div>
                    <p className="text-sm text-gray-500">MOQ</p>
                    <p className="text-lg font-semibold">{String(moq)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Múltiplo</p>
                    <p className="text-lg font-semibold">{String(multiplo)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Z Servicio</p>
                    <p className="text-lg font-semibold">{String(z)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Activo</p>
                    <p className="text-lg font-semibold">{String(activo)}</p>
                  </div>
                </div>
              </section>

              {/* Features 12m */}
              <section className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  Métricas (12m)
                </h3>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Meses Obs.</p>
                    <p className="text-lg font-semibold">{String(mesesObs)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Meses c/ Venta</p>
                    <p className="text-lg font-semibold">{String(mesesConVenta)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Demanda Mensual</p>
                    <p className="text-lg font-semibold">{fmtNum(demandaMensual, 2)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Sigma Mensual</p>
                    <p className="text-lg font-semibold">{fmtNum(sigmaMensual, 2)}</p>
                  </div>

                  <div>
                    <p className="text-sm text-gray-500">Eventos</p>
                    <p className="text-lg font-semibold">{String(eventos12m)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Q por Evento</p>
                    <p className="text-lg font-semibold">{fmtNum(qEvento, 2)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Revenue prom/evento</p>
                    <p className="text-lg font-semibold">{fmtUSD(revenueProm)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Margen total 12m</p>
                    <p className="text-lg font-semibold">{fmtUSD(margenTotal)}</p>
                  </div>
                </div>
              </section>

              {/* Eventos */}
              <section className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
                  <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5l2 2h5a2 2 0 012 2v12a2 2 0 01-2 2z" />
                  </svg>
                  Historial de Eventos ({eventos.length})
                </h3>

                {eventos.length === 0 ? (
                  <p className="text-sm text-gray-600">Sin eventos para mostrar.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-600">
                          <th className="py-2 pr-4">Fecha</th>
                          <th className="py-2 pr-4">FAC</th>
                          <th className="py-2 pr-4">Cliente</th>
                          <th className="py-2 pr-4 text-right">Qty</th>
                          <th className="py-2 pr-4 text-right">Revenue USD</th>
                          <th className="py-2 pr-0 text-right">Margin USD</th>
                        </tr>
                      </thead>
                      <tbody className="text-gray-900">
                        {eventos.slice(0, 50).map((ev, idx) => {
                          const fecha = getEv(ev, 'Fecha');
                          const fac = getEv(ev, 'FAC');
                          const cliente = getEv(ev, 'ClienteNombre');
                          const qty = getEv(ev, 'Qty');
                          const revenue = getEv(ev, 'Revenue_USD');
                          const margin = getEv(ev, 'Margin_USD');

                          return (
                            <tr key={idx} className="border-t border-gray-200">
                              <td className="py-2 pr-4">{fmtDate(fecha)}</td>
                              <td className="py-2 pr-4 font-mono">{fac ?? '-'}</td>
                              <td className="py-2 pr-4">{cliente ?? '-'}</td>
                              <td className="py-2 pr-4 text-right">{fmtNum(qty, 0)}</td>
                              <td className="py-2 pr-4 text-right">{fmtUSD(revenue)}</td>
                              <td className="py-2 pr-0 text-right">{fmtUSD(margin)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>

                    {eventos.length > 50 ? (
                      <p className="text-xs text-gray-500 mt-2">
                        Mostrando los primeros 50 eventos (para performance).
                      </p>
                    ) : null}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
