import { useState, useEffect, useRef, useCallback } from 'react';
import { SKUDetail } from '../types';

interface CacheEntry {
  data: SKUDetail;
  timestamp: number;
}

interface UseSKUCacheReturn {
  data: SKUDetail | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const cache = new Map<string, CacheEntry>();

export function useSKUCache(
  sku: string | null,
  fetchFn: (sku: string) => Promise<SKUDetail>
): UseSKUCacheReturn {
  const [data, setData] = useState<SKUDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isBackgroundRefresh = useRef(false);

  const fetchData = useCallback(
    async (forceRefresh = false) => {
      if (!sku) {
        setData(null);
        return;
      }

      const cachedEntry = cache.get(sku);
      const now = Date.now();

      // Return cached data if valid and not forcing refresh
      if (!forceRefresh && cachedEntry && now - cachedEntry.timestamp < CACHE_TTL) {
        setData(cachedEntry.data);
        return;
      }

      // Check if we should do background refresh (stale-while-revalidate)
      const shouldBackgroundRefresh =
        cachedEntry && now - cachedEntry.timestamp >= CACHE_TTL && !isBackgroundRefresh.current;

      if (shouldBackgroundRefresh) {
        isBackgroundRefresh.current = true;
        // Return stale data immediately
        setData(cachedEntry.data);
      } else if (!isBackgroundRefresh.current) {
        setIsLoading(true);
      }

      setError(null);
      // 🔒 Guard: si el caller pasó algo que no es función, evitamos el crash
      if (typeof fetchFn !== 'function') {
        setError('Configuración inválida: fetchFn no es una función (revisar apiClient.getSKUDetail)');
        setIsLoading(false);
        isBackgroundRefresh.current = false;
        return;
      }

      try {
        const result = await fetchFn(sku);
        cache.set(sku, { data: result, timestamp: now });
        setData(result);
      } catch (err) {
        // If background refresh fails, keep stale data
        if (!isBackgroundRefresh.current) {
          setError(err instanceof Error ? err.message : 'An error occurred');
        }
      } finally {
        if (!isBackgroundRefresh.current) {
          setIsLoading(false);
        }
        isBackgroundRefresh.current = false;
      }
    },
    [sku, fetchFn]
  );

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refresh = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refresh,
  };
}

// Utility to clear the entire cache
export function clearSKUCache(): void {
  cache.clear();
}

// Utility to remove a specific SKU from cache
export function invalidateSKUCache(sku: string): void {
  cache.delete(sku);
}
