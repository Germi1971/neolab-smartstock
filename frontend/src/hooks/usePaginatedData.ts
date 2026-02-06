import { useState, useEffect, useCallback } from 'react';
import { PaginationParams, SortConfig, ApiListResponse } from '../types';

interface UsePaginatedDataOptions<T, F> {
  fetchFn: (params: PaginationParams & F) => Promise<T>;
  filters?: F;
  initialPage?: number;
  initialPageSize?: number;
  initialSortKey?: string;
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

  const fetchData = useCallback(async () => {
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

      const result = await fetchFn(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [fetchFn, page, pageSize, sortConfig, filters, refreshKey]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize);
    setPage(1); // Reset to first page when changing page size
  }, []);

  const handleSort = useCallback((key: string) => {
    setSortConfig((current) => ({
      key,
      direction:
        current.key === key && current.direction === 'asc' ? 'desc' : 'asc',
    }));
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
      totalPages: data?.total_pages || 1,
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
