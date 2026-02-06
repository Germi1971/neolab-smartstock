import {
  PaginationParams,
  ApiListResponse,
  StockItem,
  StockFilters,
  PurchaseSuggestion,
  PurchaseFilters,
  ApproveRequest,
  SKUParameter,
  ParameterFilters,
  MLRun,
  MLRunFilters,
  MLModelInfo,
  MLFeatures,
  SKUDetail,
  HealthResponse,
  MLRunResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    // Handle blob responses (exports)
    if (options.headers?.['Accept'] === 'text/csv') {
      return response.blob() as Promise<T>;
    }

    return response.json();
  }

  private buildQueryString(params: Record<string, unknown>): string {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        query.append(key, String(value));
      }
    });
    const queryString = query.toString();
    return queryString ? `?${queryString}` : '';
  }

  // ==================== Stock Endpoints ====================

  async getStock(
    params: PaginationParams & StockFilters = {}
  ): Promise<ApiListResponse<StockItem>> {
    return this.request(`/stock${this.buildQueryString(params)}`);
  }

  async getStockBySKU(sku: string): Promise<StockItem> {
    return this.request(`/stock/${encodeURIComponent(sku)}`);
  }

  // ==================== Purchase Suggestions Endpoints ====================

  async getPurchaseSuggestions(
    params: PaginationParams & PurchaseFilters = {}
  ): Promise<ApiListResponse<PurchaseSuggestion>> {
    return this.request(`/purchases/suggestions${this.buildQueryString(params)}`);
  }

  async getSuggestionBySKU(sku: string): Promise<PurchaseSuggestion> {
    return this.request(`/purchases/suggestions/${encodeURIComponent(sku)}`);
  }

  async approveSuggestion(
    sku: string,
    data: ApproveRequest
  ): Promise<PurchaseSuggestion> {
    return this.request(`/purchases/suggestions/${encodeURIComponent(sku)}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async unapproveSuggestion(sku: string): Promise<PurchaseSuggestion> {
    return this.request(`/purchases/suggestions/${encodeURIComponent(sku)}/unapprove`, {
      method: 'POST',
    });
  }

  async exportPurchaseOrder(
    params: PurchaseFilters & { limit?: number } = {}
  ): Promise<Blob> {
    return this.request(`/purchases/export${this.buildQueryString(params)}`, {
      headers: { Accept: 'text/csv' },
    });
  }

  // ==================== SKU Parameters Endpoints ====================

  async getSKUParameters(
    params: PaginationParams & ParameterFilters = {}
  ): Promise<ApiListResponse<SKUParameter>> {
    return this.request(`/parameters${this.buildQueryString(params)}`);
  }

  async getSKUParameter(sku: string): Promise<SKUParameter> {
    return this.request(`/parameters/${encodeURIComponent(sku)}`);
  }

  async updateSKUParameter(
    sku: string,
    data: Partial<SKUParameter>
  ): Promise<SKUParameter> {
    return this.request(`/parameters/${encodeURIComponent(sku)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async bulkUpdateSKUParameters(
    data: Array<{ sku: string } & Partial<SKUParameter>>
  ): Promise<{ updated: number }> {
    return this.request('/parameters/bulk', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // ==================== ML Endpoints ====================

  async getMLRuns(
    params: PaginationParams & MLRunFilters = {}
  ): Promise<ApiListResponse<MLRun>> {
    return this.request(`/ml/runs${this.buildQueryString(params)}`);
  }

  async getMLRun(runId: string): Promise<MLRun> {
    return this.request(`/ml/runs/${encodeURIComponent(runId)}`);
  }

  async getMLModels(
    params: PaginationParams = {}
  ): Promise<ApiListResponse<MLModelInfo>> {
    return this.request(`/ml/models${this.buildQueryString(params)}`);
  }

  async getMLModelBySKU(sku: string): Promise<MLModelInfo> {
    return this.request(`/ml/models/${encodeURIComponent(sku)}`);
  }

  async getMLFeatures(sku: string): Promise<MLFeatures> {
    return this.request(`/ml/features/${encodeURIComponent(sku)}`);
  }

  async runMLPipeline(): Promise<MLRunResponse> {
    return this.request('/ml/run', {
      method: 'POST',
    });
  }

  // ==================== SKU Detail Endpoint ====================

  async getSKUDetail(sku: string): Promise<SKUDetail> {
    return this.request(`/sku/${encodeURIComponent(sku)}/detail`);
  }

  // ==================== Health Endpoints ====================

  async getHealth(): Promise<HealthResponse> {
    return this.request('/health');
  }

  async getMetrics(): Promise<Record<string, unknown>> {
    return this.request('/metrics');
  }
}

export const apiClient = new ApiClient();
export default apiClient;
