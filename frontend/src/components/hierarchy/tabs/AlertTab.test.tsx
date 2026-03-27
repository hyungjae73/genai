import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import AlertTab, { 
  getSeverityBadgeClass, 
  getSeverityLabel, 
  filterAlertsByStatus 
} from './AlertTab';
import * as api from '../../../services/api';
import type { Alert } from '../../../services/api';

// Mock the API module
vi.mock('../../../services/api', () => ({
  getSiteAlerts: vi.fn(),
}));

describe('AlertTab', () => {
  const mockAlerts: Alert[] = [
    {
      id: 1,
      site_id: 1,
      site_name: 'Test Site',
      severity: 'high',
      message: 'Price mismatch detected',
      alert_type: 'violation',
      violation_type: 'price_violation',
      created_at: '2024-01-15T10:00:00Z',
      is_resolved: false,
    },
    {
      id: 2,
      site_id: 1,
      site_name: 'Test Site',
      severity: 'low',
      message: 'Minor formatting issue',
      alert_type: 'violation',
      violation_type: 'format_violation',
      created_at: '2024-01-14T09:00:00Z',
      is_resolved: true,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Pure Functions', () => {
    it('getSeverityBadgeClass returns correct CSS class for each severity level', () => {
      expect(getSeverityBadgeClass('low')).toBe('severity-badge severity-low');
      expect(getSeverityBadgeClass('medium')).toBe('severity-badge severity-medium');
      expect(getSeverityBadgeClass('high')).toBe('severity-badge severity-high');
      expect(getSeverityBadgeClass('critical')).toBe('severity-badge severity-critical');
    });

    it('getSeverityLabel returns correct Japanese label for each severity level', () => {
      expect(getSeverityLabel('low')).toBe('低');
      expect(getSeverityLabel('medium')).toBe('中');
      expect(getSeverityLabel('high')).toBe('高');
      expect(getSeverityLabel('critical')).toBe('緊急');
    });

    it('filterAlertsByStatus filters alerts correctly', () => {
      const allAlerts = filterAlertsByStatus(mockAlerts, 'all');
      expect(allAlerts).toHaveLength(2);

      const unresolvedAlerts = filterAlertsByStatus(mockAlerts, 'unresolved');
      expect(unresolvedAlerts).toHaveLength(1);
      expect(unresolvedAlerts[0].is_resolved).toBe(false);

      const resolvedAlerts = filterAlertsByStatus(mockAlerts, 'resolved');
      expect(resolvedAlerts).toHaveLength(1);
      expect(resolvedAlerts[0].is_resolved).toBe(true);
    });
  });

  describe('Component Rendering', () => {
    it('displays loading state initially', () => {
      vi.mocked(api.getSiteAlerts).mockImplementation(() => new Promise(() => {}));
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });

    it('displays error message when API call fails', async () => {
      vi.mocked(api.getSiteAlerts).mockRejectedValue(new Error('API Error'));
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      await waitFor(() => {
        expect(screen.getByText(/エラー:/)).toBeInTheDocument();
      });
    });

    it('displays empty state when no alerts exist', async () => {
      vi.mocked(api.getSiteAlerts).mockResolvedValue([]);
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      await waitFor(() => {
        expect(screen.getByText('アラートがありません')).toBeInTheDocument();
      });
    });

    it('displays alerts with correct information', async () => {
      vi.mocked(api.getSiteAlerts).mockResolvedValue(mockAlerts);
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      await waitFor(() => {
        expect(screen.getAllByText('Test Customer')).toHaveLength(2);
        expect(screen.getByText('Price mismatch detected')).toBeInTheDocument();
        expect(screen.getByText('Minor formatting issue')).toBeInTheDocument();
      });
    });

    it('displays severity badges correctly', async () => {
      vi.mocked(api.getSiteAlerts).mockResolvedValue(mockAlerts);
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      await waitFor(() => {
        expect(screen.getByText('高')).toBeInTheDocument(); // high severity
        expect(screen.getByText('低')).toBeInTheDocument(); // low severity
      });
    });

    it('displays resolution status correctly', async () => {
      vi.mocked(api.getSiteAlerts).mockResolvedValue(mockAlerts);
      
      render(<AlertTab siteId={1} customerName="Test Customer" />);
      
      await waitFor(() => {
        // Check for status badges (not the filter options)
        const statusBadges = screen.getAllByText('未解決');
        const resolvedBadges = screen.getAllByText('解決済み');
        
        // Should have at least one of each (one in filter, one in badge)
        expect(statusBadges.length).toBeGreaterThanOrEqual(1);
        expect(resolvedBadges.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('displays "偽サイト" badge with fake-site class for fake_site alerts', async () => {
      const fakeSiteAlerts: Alert[] = [
        {
          id: 10,
          site_id: 1,
          site_name: 'Test Site',
          severity: 'critical',
          message: 'Fake site detected',
          alert_type: 'fake_site',
          violation_type: 'fake_site',
          created_at: '2024-01-15T10:00:00Z',
          is_resolved: false,
        },
      ];
      vi.mocked(api.getSiteAlerts).mockResolvedValue(fakeSiteAlerts);

      render(<AlertTab siteId={1} customerName="Test Customer" />);

      await waitFor(() => {
        const badge = screen.getByText('偽サイト');
        expect(badge).toBeInTheDocument();
        expect(badge.className).toBe('alert-type-badge fake-site');
      });
    });

    it('displays "契約違反" badge with violation class for non-fake_site alerts', async () => {
      const violationAlerts: Alert[] = [
        {
          id: 11,
          site_id: 1,
          site_name: 'Test Site',
          severity: 'medium',
          message: 'Violation detected',
          alert_type: 'violation',
          violation_type: 'price_violation',
          created_at: '2024-01-15T10:00:00Z',
          is_resolved: false,
        },
      ];
      vi.mocked(api.getSiteAlerts).mockResolvedValue(violationAlerts);

      render(<AlertTab siteId={1} customerName="Test Customer" />);

      await waitFor(() => {
        const badge = screen.getByText('契約違反');
        expect(badge).toBeInTheDocument();
        expect(badge.className).toBe('alert-type-badge violation');
      });
    });
  });
});
