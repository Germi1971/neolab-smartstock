import { useEffect, useRef, useState } from 'react';
import { Chart, ChartConfiguration, registerables } from 'chart.js';
import { apiClient, ChartDataResponse } from '../services/apiClient';

Chart.register(...registerables);

interface SKUChartsProps {
  sku: string;
  isVisible: boolean;
}

function fmtNum(v: number, digits = 0): string {
  if (!Number.isFinite(v)) return '-';
  return v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function SKUCharts({ sku, isVisible }: SKUChartsProps) {
  const [data, setData] = useState<ChartDataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const chartStockRef = useRef<HTMLCanvasElement>(null);
  const chartDemandRef = useRef<HTMLCanvasElement>(null);
  const chartStockInstance = useRef<Chart | null>(null);
  const chartDemandInstance = useRef<Chart | null>(null);

  useEffect(() => {
    if (!sku || !isVisible) return;
    setLoading(true);
    setError(null);
    apiClient
      .getSKUChartData(sku)
      .then(setData)
      .catch((e) => setError(e?.message || 'Error al cargar datos'))
      .finally(() => setLoading(false));
  }, [sku, isVisible]);

  // Render chart 2: Stock vs umbrales
  useEffect(() => {
    if (!data || !chartStockRef.current) return;

    if (chartStockInstance.current) {
      chartStockInstance.current.destroy();
      chartStockInstance.current = null;
    }

    const hasProyeccion = data.proyeccion_meses.length > 0;
    const stockLabels = ['Hoy', ...(hasProyeccion ? data.proyeccion_meses.map((p) => `M+${p.month}`) : [])];
    const stockData = [
      data.stock_actual,
      ...(hasProyeccion ? data.proyeccion_meses.map((p) => p.stock_proyectado) : []),
    ];

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels: stockLabels,
        datasets: [
          {
            label: 'Stock (actual + proyección)',
            data: stockData,
            borderColor: 'rgb(34, 197, 94)',
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            fill: true,
            tension: 0.3,
          },
          {
            label: 'Punto de reorden',
            data: stockLabels.map(() => data.stock_min),
            borderColor: 'rgb(239, 68, 68)',
            borderDash: [5, 5],
            fill: false,
          },
          {
            label: 'Stock objetivo',
            data: stockLabels.map(() => data.stock_objetivo),
            borderColor: 'rgb(59, 130, 246)',
            borderDash: [5, 5],
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true } },
      },
    };

    chartStockInstance.current = new Chart(chartStockRef.current, config);
    return () => {
      chartStockInstance.current?.destroy();
      chartStockInstance.current = null;
    };
  }, [data]);

  // Render chart 1: Demanda histórica
  useEffect(() => {
    if (!data || !chartDemandRef.current) return;
    const hasHistorico = data.demanda_historica.length > 0;
    const hasProyeccion = data.proyeccion_meses.length > 0;
    if (!hasHistorico && !hasProyeccion) return;

    if (chartDemandInstance.current) {
      chartDemandInstance.current.destroy();
      chartDemandInstance.current = null;
    }

    const demandaProm = data.demanda_prom_mensual || data.demand_p90 / 6;
    const labels = hasHistorico
      ? data.demanda_historica.map((d) => d.month)
      : [];
    const histData = hasHistorico
      ? data.demanda_historica.map((d) => d.qty)
      : [];
    const proyLabels = hasProyeccion ? data.proyeccion_meses.map((p) => `M+${p.month}`) : [];
    const proyData = hasProyeccion ? data.proyeccion_meses.map(() => demandaProm) : [];

    const allLabels = [...labels, ...proyLabels];
    const barData = [...histData, ...proyLabels.map(() => 0)];
    const lineData = [...labels.map(() => null as number | null), ...proyData];

    const config: ChartConfiguration<'bar'> = {
      type: 'bar',
      data: {
        labels: allLabels,
        datasets: [
          {
            type: 'bar',
            label: 'Demanda histórica',
            data: barData,
            backgroundColor: 'rgba(59, 130, 246, 0.6)',
            borderColor: 'rgb(59, 130, 246)',
            borderWidth: 1,
          },
          {
            type: 'line',
            label: 'Proyección estimada (uds/mes)',
            data: lineData,
            borderColor: 'rgb(234, 179, 8)',
            backgroundColor: 'rgba(234, 179, 8, 0.1)',
            fill: true,
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: { y: { beginAtZero: true } },
      },
    };

    chartDemandInstance.current = new Chart(chartDemandRef.current, config);
    return () => {
      chartDemandInstance.current?.destroy();
      chartDemandInstance.current = null;
    };
  }, [data]);

  if (!isVisible) return null;
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 rounded-lg">
        {error}
      </div>
    );
  }
  if (!data) return null;

  const hasHistorico = data.demanda_historica.length > 0;
  const hasProyeccion = data.proyeccion_meses.length > 0;
  const hasDemandChart = hasHistorico || hasProyeccion;

  return (
    <section className="bg-gray-50 rounded-lg p-4 space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
        <svg
          className="w-5 h-5 text-indigo-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
        Situación del SKU
      </h3>

      {/* KPIs rápidos */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <p className="text-xs text-gray-500">Stock actual</p>
          <p className="text-lg font-bold text-gray-900">{fmtNum(data.stock_actual, 0)}</p>
        </div>
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <p className="text-xs text-gray-500">Pto. reorden</p>
          <p className="text-lg font-bold text-red-600">{fmtNum(data.stock_min, 0)}</p>
        </div>
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <p className="text-xs text-gray-500">Stock objetivo</p>
          <p className="text-lg font-bold text-blue-600">{fmtNum(data.stock_objetivo, 0)}</p>
        </div>
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <p className="text-xs text-gray-500">P(stockout)</p>
          <p className="text-lg font-bold text-amber-600">
            {(data.p_stockout * 100).toFixed(1)}%
          </p>
        </div>
      </div>

      {/* Gráfico Stock vs umbrales */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <h4 className="text-sm font-medium text-gray-700 mb-3">
          Stock actual y proyección a 6 meses
        </h4>
        <div className="h-64">
          <canvas ref={chartStockRef} />
        </div>
      </div>

      {/* Gráfico Demanda histórica */}
      {hasDemandChart && (
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-3">
            Demanda histórica y estimada (uds/mes)
          </h4>
          <div className="h-64">
            <canvas ref={chartDemandRef} />
          </div>
        </div>
      )}

      {/* Percentiles de demanda */}
      {(data.demand_p50 > 0 || data.demand_p90 > 0) && (
        <div className="bg-white rounded-lg p-4 border border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Percentiles de demanda (horizonte {data.horizon_days} días)
          </h4>
          <div className="flex gap-4 text-sm">
            <span>
              P50: <strong>{fmtNum(data.demand_p50, 1)}</strong> uds
            </span>
            <span>
              P80: <strong>{fmtNum(data.demand_p80, 1)}</strong> uds
            </span>
            <span>
              P90: <strong>{fmtNum(data.demand_p90, 1)}</strong> uds
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
