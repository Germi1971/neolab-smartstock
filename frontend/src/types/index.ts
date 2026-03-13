// ==================== Base Types ====================

export interface PaginationParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiListResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  stats?: Record<string, number>;
}

// ==================== Stock Types ====================

export interface StockItem {
  sku: string;
  descripcion: string;
  stock_posicion: number;
  stock_objetivo: number;
  stock_seguridad: number;
  punto_reorden: number;
  moq: number | null;
  multiplo: number | null;
  activo: boolean;
  updated_at: string;
}

export interface StockFilters {
  sku?: string;
  descripcion?: string;
  activo?: string;
  stock_bajo?: string;
}

// ==================== Purchase Types ====================

export interface PurchaseSuggestion {
  [key: string]: any;
  sku: string;
  descripcion: string;
  stock_posicion: number;
  stock_objetivo: number;
  stock_objetivo_calculado: number;
  qty_sugerida: number;
  qty_final: number | null;
  estado: 'PENDIENTE' | 'APROBADO' | 'RECHAZADO';
  modelo_seleccionado: string;
  s_policy: number | null;
  S_policy: number | null;
  notas: string | null;
  aprobado_por: string | null;
  fecha_aprobacion: string | null;
  updated_at: string;
}

export interface ApproveRequest {
  qty_final: number;
  notas?: string;
}

export interface PurchaseFilters {
  [key: string]: any;
  sku?: string;
  descripcion?: string;
  estado?: string;
  modelo?: string;
}

// ==================== Parameter Types ====================

export interface SKUParameter {
  sku: string;
  descripcion: string;
  stock_objetivo: number;
  stock_seguridad: number;
  punto_reorden: number;
  moq: number | null;
  multiplo: number | null;
  activo: boolean;
  updated_at: string;
}

export interface ParameterFilters {
  sku?: string;
  descripcion?: string;
  activo?: string;
  tiene_moq?: string;
}

// ==================== ML Types ====================

export interface MLRun {
  [key: string]: any;
  run_id: string;
  started_at: string;
  finished_at: string | null;
  skus_procesados: number;
  skus_exitosos: number;
  skus_fallidos: number;
  duracion_segundos: number | null;
  triggered_by: 'SCHEDULER' | 'MANUAL' | 'API';
  error_log: Record<string, unknown> | null;
}

export interface MLRunFilters {
  [key: string]: any;
  status?: string;
  triggered_by?: string;
  fecha_desde?: string;
  fecha_hasta?: string;
}

export interface MLModelInfo {
  [key: string]: any;
  sku: string;
  modelo_actual: string;
  modelo_anterior: string | null;
  fecha_seleccion: string;
  score_composite: number;
  cv_12m: number;
  lambda_eventos_mes_12m: number;
  drift_detected: boolean;
}

export interface MLFeatures {
  sku: string;
  run_id: string;
  periodo_inicio: string;
  periodo_fin: string;
  dias_observados_12m: number;
  eventos_12m: number;
  unidades_12m: number;
  meses_con_venta_12m: number;
  pct_meses_con_venta_12m: number;
  lambda_eventos_mes_12m: number;
  mu_unidades_evento_12m: number;
  cv_12m: number;
  adi_12m: number;
  squared_cv_12m: number;
  dias_observados_24m: number;
  eventos_24m: number;
  unidades_24m: number;
  cv_24m: number;
  dias_observados_90d: number;
  eventos_90d: number;
  unidades_90d: number;
  tendencia_90d: number;
  ultima_venta: string;
  dias_desde_ultima_venta: number;
}

export interface SKUDetail {
  sku: string;
  descripcion: string;
  stock: StockItem;
  parameters: SKUParameter;
  suggestion: PurchaseSuggestion | null;
  features: MLFeatures | null;
  model: MLModelInfo | null;
}

// ==================== Sort Types ====================

export interface SortConfig {
  key: string | null;
  direction: 'asc' | 'desc';
}

// ==================== API Response Types ====================

export interface HealthResponse {
  status: string;
  version: string;
  database: string;
  ml_pipeline: string;
  timestamp: string;
}

export interface MLRunResponse {
  run_id: string;
  status: string;
  message: string;
}
