/**
 * API client functions for extracted payment information and price history.
 *
 * Uses the shared axios instance from services/api.
 */

import api from '../services/api';
import type {
  ExtractedPaymentInfo,
  ExtractedPaymentInfoUpdate,
  PaginatedExtractedPaymentInfo,
  PriceHistoryList,
  AuditLogEntry,
} from '../types/extractedData';

/**
 * Fetch extracted payment info for a specific crawl result.
 *
 * GET /api/extracted-data/{crawlResultId}
 */
export const fetchExtractedData = async (
  crawlResultId: number,
): Promise<ExtractedPaymentInfo> => {
  const response = await api.get<ExtractedPaymentInfo>(
    `/api/extracted-data/${crawlResultId}`,
  );
  return response.data;
};

/**
 * Fetch all extracted payment info for a site (paginated).
 *
 * GET /api/extracted-data/site/{siteId}
 */
export const fetchSiteExtractedData = async (
  siteId: number,
  page: number = 1,
  pageSize: number = 50,
): Promise<PaginatedExtractedPaymentInfo> => {
  const response = await api.get<PaginatedExtractedPaymentInfo>(
    `/api/extracted-data/site/${siteId}`,
    { params: { page, page_size: pageSize } },
  );
  return response.data;
};

/**
 * Update extracted payment info fields (manual correction).
 *
 * PUT /api/extracted-data/{id}
 */
export const updateExtractedData = async (
  id: number,
  updates: ExtractedPaymentInfoUpdate,
): Promise<ExtractedPaymentInfo> => {
  const response = await api.put<ExtractedPaymentInfo>(
    `/api/extracted-data/${id}`,
    updates,
  );
  return response.data;
};

/**
 * Fetch price history for a product on a site.
 *
 * GET /api/price-history/{siteId}/{productId}
 * Supports optional date-range filtering.
 */
export const fetchPriceHistory = async (
  siteId: number,
  productId: string,
  startDate?: string,
  endDate?: string,
): Promise<PriceHistoryList> => {
  const params: Record<string, string> = {};
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;

  const response = await api.get<PriceHistoryList>(
    `/api/price-history/${siteId}/${encodeURIComponent(productId)}`,
    { params },
  );
  return response.data;
};

/**
 * Approve extracted payment info.
 *
 * POST /api/extracted-data/{id}/approve
 */
export const approveExtractedData = async (
  id: number,
): Promise<void> => {
  await api.post(`/api/extracted-data/${id}/approve`);
};

/**
 * Reject extracted payment info with a reason.
 *
 * POST /api/extracted-data/{id}/reject
 */
export const rejectExtractedData = async (
  id: number,
  reason: string,
): Promise<void> => {
  await api.post(`/api/extracted-data/${id}/reject`, { reason });
};

/**
 * Fetch audit logs for a specific entity.
 *
 * GET /api/audit-logs/{entityType}/{entityId}
 * Returns empty array if the endpoint is not available yet.
 */
export const fetchAuditLogs = async (
  entityType: string,
  entityId: number,
): Promise<AuditLogEntry[]> => {
  try {
    const response = await api.get<AuditLogEntry[]>(
      `/api/audit-logs/${entityType}/${entityId}`,
    );
    return response.data;
  } catch {
    // Endpoint may not exist yet – return empty list gracefully
    return [];
  }
};
