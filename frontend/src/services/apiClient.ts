// frontend/src/services/apiClient.ts

const API_BASE_URL =
  import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export type ApiError = Error & {
  request?: { url: string; method: string };
  response?: { status: number; data: any };
};

import { PurchaseSuggestion, ApiListResponse } from '../types';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  // =========================================================
  // Core request
  // =========================================================
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const method = (options.method || 'GET').toUpperCase();

    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
      });

      const contentType = response.headers.get('content-type') || '';
      const isJson = contentType.includes('application/json');
      const data: any = isJson ? await response.json() : await response.text();

      if (!response.ok) {
        const err: ApiError = new Error(
          data?.detail || data?.message || `HTTP ${response.status}`
        );
        err.request = { url, method };
        err.response = { status: response.status, data };
        throw err;
      }

      return data as T;
    } catch (e: any) {
      if (e?.request || e?.response) throw e;

      const err: ApiError = new Error(e?.message || 'Network error');
      err.request = { url, method };
      err.response = { status: 0, data: null };
      throw err;
    }
  }

  // =========================================================
  // HEALTH
  // =========================================================
  async healthCheck() {
    return this.request('/health');
  }

  // =========================================================
  // STOCK
  // =========================================================
  async getStock(params: Record<string, any>) {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    return this.request(`/api/stock?${qp.toString()}`);
  }

  async getSKUParameters(params: Record<string, any>) {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    return this.request(`/api/parameters?${qp.toString()}`);
  }

  async updateSKUParameter(sku: string, updates: Partial<any>) {
    return this.request(`/api/parameters/${encodeURIComponent(sku)}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async getPurchaseSuggestions(params: Record<string, any>): Promise<ApiListResponse<PurchaseSuggestion>> {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    return this.request<ApiListResponse<PurchaseSuggestion>>(`/api/purchases/suggestions?${qp.toString()}`);
  }

  // =========================================================
  // ML – RUNS & PIPELINE
  // =========================================================
  async getMLRuns(params: Record<string, any>) {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    return this.request(`/api/ml/runs?${qp.toString()}`);
  }

  async runMLPipeline(payload: { sku?: string; skus?: string[] } = {}) {
    return this.request('/api/ml/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getMLModels(params: Record<string, any> = {}) {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    return this.request(`/api/ml/models?${qp.toString()}`);
  }

  async getSKUDetail(sku: string) {
    if (!sku) throw new Error('SKU vacío');
    return this.request(`/api/ml/sku/${encodeURIComponent(sku)}`);
  }

  async approveSuggestion(sku: string, payload: { qty_final: number; notas?: string }) {
    return this.request(`/api/purchases/approve/${encodeURIComponent(sku)}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async unapproveSuggestion(sku: string) {
    return this.request(`/api/purchases/unapprove/${encodeURIComponent(sku)}`, {
      method: 'POST',
    });
  }

  async exportPurchaseOrder(params: Record<string, any>) {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        qp.append(k, String(v));
      }
    });
    const url = `${this.baseUrl}/api/purchases/export?${qp.toString()}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Export failed');
    return response.blob();
  }

  async syncMLSuggestions(payload: { run_id?: string; sku?: string } = {}) {
    return this.request<{ ok: boolean; updated_count: number; message: string }>('/api/ml/suggestions/sync', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getSKUFeatures(sku: string) {
    return this.request(`/api/ml/features/${encodeURIComponent(sku)}`);
  }
}

export const apiClient = new ApiClient();
export default apiClient;
