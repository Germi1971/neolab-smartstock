import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { PaginationParams, SortConfig, ApiListResponse } from '../types';

interface UsePaginatedDataOptions<T, F> {
  fetchFn: (params: PaginationParams & F) => Promise<T>;
  filters?: F;
  initialPage?: number;
  initialPageSize?: number;
  initialSortKey?: string | null;
  initialSortDirection?: 'asc' | 'desc';
}

interface UsePaginatedDataReturn<T> {
  data: T | null;
  pagination: {
    page: number;
    pageSize: number;
    totalItems: number;
    totalPages: number;
  };
  sortConfig: SortConfig;
  isLoading: boolean;
  error: string | null;
  handlePageChange: (page: number) => void;
  handlePageSizeChange: (pageSize: number) => void;
  handleSort: (key: string) => void;
  refresh: () => void;
}

export function usePaginatedData<T extends ApiListResponse<unknown>, F>(
  options: UsePaginatedDataOptions<T, F>
): UsePaginatedDataReturn<T> {
  const {
    fetchFn,
    filters = {} as F,
    initialPage = 1,
    initialPageSize = 25,
    initialSortKey = null,
    initialSortDirection = 'asc',
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [page, setPage] = useState(initialPage);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: initialSortKey,
    direction: initialSortDirection,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  /**
   * 🔒 FIX 1: estabiliza filters para dependencias
   */
  const filtersKey = useMemo(() => JSON.stringify(filters ?? {}), [filters]);

  /**
   * 🔒 FIX 2 (anti-loop definitivo): fetchFn en ref
   * Aunque el componente cree fetchFn inline en cada render,
   * NO dispara nuevos fetch por el identity-change.
   */
  const fetchFnRef = useRef(fetchFn);
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  }, [fetchFn]);

  /**
   * 🔒 FIX 3: evitar requests simultáneos si el render se acelera
   */
  const inFlightRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    // cancela el request anterior si aún está corriendo
    if (inFlightRef.current) {
      inFlightRef.current.abort();
    }
    const controller = new AbortController();
    inFlightRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const params: PaginationParams & F = {
        page,
        page_size: pageSize,
        ...(sortConfig.key && {
          sort_by: sortConfig.key,
          sort_order: sortConfig.direction,
        }),
        ...filters,
      };

      /**
       * NOTA: si tu fetchFn usa fetch() nativo y soporta AbortSignal,
       * podrías pasar signal dentro de params o como arg extra.
       * Como acá tu fetchFn firma (params) => Promise<T>,
       * solo abortamos para evitar setState de requests viejos.
       */
      const result = await fetchFnRef.current(params);

      // si fue abortado, no tocar state
      if (controller.signal.aborted) return;

      setData(result);
    } catch (err) {
      // si fue abortado, ignorar
      if (controller.signal.aborted) return;

      setError(err instanceof Error ? err.message : 'An error occurred');
      setData(null);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, [
    page,
    pageSize,
    sortConfig.key,
    sortConfig.direction,
    filtersKey,   // <- depende del contenido de filters, no de la ref
    refreshKey,
    // NO fetchFn acá
  ]);

  useEffect(() => {
    fetchData();
    return () => {
      // cleanup: aborta si el componente desmonta
      if (inFlightRef.current) inFlightRef.current.abort();
    };
  }, [fetchData]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1);
  }, []);

  const handleSort = useCallback((key: string) => {
    setSortConfig((current) => ({
      key,
      direction:
        current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
    setPage(1);
  }, []);

  const refresh = useCallback(() => {
    setRefreshKey((prev) => prev + 1);
  }, []);

  return {
    data,
    pagination: {
      page,
      pageSize,
      totalItems: data?.total || 0,
      totalPages:
        data?.total_pages ??
        Math.max(1, Math.ceil((data?.total || 0) / pageSize)),
    },
    sortConfig,
    isLoading,
    error,
    handlePageChange,
    handlePageSizeChange,
    handleSort,
    refresh,
  };
}

