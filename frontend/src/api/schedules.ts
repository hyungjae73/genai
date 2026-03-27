/**
 * API client functions for crawl schedule management.
 *
 * Uses the shared axios instance from services/api.
 */

import api from '../services/api';

export interface CrawlScheduleData {
  site_id: number;
  priority: 'high' | 'normal' | 'low';
  interval_minutes: number;
  next_crawl_at: string;
  last_etag: string | null;
  last_modified: string | null;
}

export interface CreateScheduleRequest {
  priority: 'high' | 'normal' | 'low';
  interval_minutes: number;
}

export interface UpdateScheduleRequest {
  priority?: 'high' | 'normal' | 'low';
  interval_minutes?: number;
}

export interface UpdateSiteSettingsRequest {
  pre_capture_script?: unknown | null;
  crawl_priority?: 'high' | 'normal' | 'low';
  plugin_config?: Record<string, unknown> | null;
}

/**
 * Fetch crawl schedule for a site.
 *
 * GET /api/sites/{siteId}/schedule
 */
export const getSchedule = async (siteId: number): Promise<CrawlScheduleData> => {
  const response = await api.get<CrawlScheduleData>(`/api/sites/${siteId}/schedule`);
  return response.data;
};

/**
 * Create a new crawl schedule for a site.
 *
 * POST /api/sites/{siteId}/schedule
 */
export const createSchedule = async (
  siteId: number,
  data: CreateScheduleRequest,
): Promise<CrawlScheduleData> => {
  const response = await api.post<CrawlScheduleData>(
    `/api/sites/${siteId}/schedule`,
    data,
  );
  return response.data;
};

/**
 * Update an existing crawl schedule for a site.
 *
 * PUT /api/sites/{siteId}/schedule
 */
export const updateSchedule = async (
  siteId: number,
  data: UpdateScheduleRequest,
): Promise<CrawlScheduleData> => {
  const response = await api.put<CrawlScheduleData>(
    `/api/sites/${siteId}/schedule`,
    data,
  );
  return response.data;
};

/**
 * Update site settings (pre_capture_script, crawl_priority, plugin_config).
 *
 * PUT /api/sites/{siteId}
 */
export const updateSiteSettings = async (
  siteId: number,
  data: UpdateSiteSettingsRequest,
): Promise<void> => {
  await api.put(`/api/sites/${siteId}`, data);
};
