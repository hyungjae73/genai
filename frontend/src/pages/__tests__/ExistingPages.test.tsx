import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Customers from '../Customers';
import Sites from '../Sites';
import Contracts from '../Contracts';
import Screenshots from '../Screenshots';
import Verification from '../Verification';
import * as api from '../../services/api';

// Mock API calls
vi.mock('../../services/api', () => ({
  getCustomers: vi.fn(),
  getSites: vi.fn(),
  getContracts: vi.fn(),
  getSiteContracts: vi.fn(),
  getSiteScreenshots: vi.fn(),
  getVerificationResults: vi.fn(),
  createCustomer: vi.fn(),
  updateCustomer: vi.fn(),
  deleteCustomer: vi.fn(),
  createSite: vi.fn(),
  updateSite: vi.fn(),
  deleteSite: vi.fn(),
  createContract: vi.fn(),
  deleteContract: vi.fn(),
  uploadScreenshot: vi.fn(),
  deleteScreenshot: vi.fn(),
  getScreenshotUrl: vi.fn(),
  triggerVerification: vi.fn(),
  getVerificationStatus: vi.fn(),
  triggerCrawl: vi.fn(),
  getCrawlStatus: vi.fn(),
  getLatestCrawlResult: vi.fn(),
}));

describe('Existing Pages - Backward Compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Customers Page', () => {
    it('should render without crashing', async () => {
      vi.mocked(api.getCustomers).mockResolvedValue([
        {
          id: 1,
          name: 'Test Customer',
          company_name: 'Test Company',
          email: 'test@example.com',
          phone: '123-456-7890',
          address: 'Test Address',
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);

      render(
        <BrowserRouter>
          <Customers />
        </BrowserRouter>
      );

      expect(await screen.findByText('顧客マスター')).toBeInTheDocument();
    });
  });

  describe('Sites Page', () => {
    it('should render without crashing', async () => {
      vi.mocked(api.getSites).mockResolvedValue([
        {
          id: 1,
          customer_id: 1,
          name: 'Test Site',
          url: 'https://example.com',
          compliance_status: 'compliant',
          is_active: true,
          last_crawled_at: '2024-01-01T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);
      vi.mocked(api.getCustomers).mockResolvedValue([
        {
          id: 1,
          name: 'Test Customer',
          company_name: 'Test Company',
          email: 'test@example.com',
          phone: '123-456-7890',
          address: 'Test Address',
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);

      render(
        <BrowserRouter>
          <Sites />
        </BrowserRouter>
      );

      expect(await screen.findByText('監視対象サイト一覧')).toBeInTheDocument();
    });
  });

  describe('Contracts Page', () => {
    it('should render without crashing', async () => {
      vi.mocked(api.getSites).mockResolvedValue([
        {
          id: 1,
          customer_id: 1,
          name: 'Test Site',
          url: 'https://example.com',
          compliance_status: 'compliant',
          is_active: true,
          last_crawled_at: '2024-01-01T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);
      vi.mocked(api.getContracts).mockResolvedValue([
        {
          id: 1,
          site_id: 1,
          version: 1,
          prices: { JPY: 1000 },
          payment_methods: { allowed: ['credit_card'], required: [] },
          fees: { percentage: 3.5, fixed: 0 },
          subscription_terms: {
            has_commitment: false,
            commitment_months: 0,
            has_cancellation_policy: false,
          },
          is_current: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);

      render(
        <BrowserRouter>
          <Contracts />
        </BrowserRouter>
      );

      expect(await screen.findByText('契約条件管理')).toBeInTheDocument();
    });
  });

  describe('Screenshots Page', () => {
    it('should render without crashing', async () => {
      vi.mocked(api.getSites).mockResolvedValue([
        {
          id: 1,
          customer_id: 1,
          name: 'Test Site',
          url: 'https://example.com',
          compliance_status: 'compliant',
          is_active: true,
          last_crawled_at: '2024-01-01T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);

      render(
        <BrowserRouter>
          <Screenshots />
        </BrowserRouter>
      );

      expect(await screen.findByText('スクリーンショット管理')).toBeInTheDocument();
    });
  });

  describe('Verification Page', () => {
    it('should render without crashing', async () => {
      vi.mocked(api.getSites).mockResolvedValue([
        {
          id: 1,
          customer_id: 1,
          name: 'Test Site',
          url: 'https://example.com',
          compliance_status: 'compliant',
          is_active: true,
          last_crawled_at: '2024-01-01T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
        },
      ]);

      render(
        <BrowserRouter>
          <Verification />
        </BrowserRouter>
      );

      expect(await screen.findByText('検証・比較システム')).toBeInTheDocument();
    });
  });
});
