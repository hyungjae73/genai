import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Verification from '../Verification';

// Mock the API module
vi.mock('../../services/api', () => ({
  getSites: vi.fn(),
  triggerVerification: vi.fn(),
  getVerificationResults: vi.fn(),
  getVerificationStatus: vi.fn(),
}));

import {
  getSites,
  triggerVerification,
  getVerificationResults,
  getVerificationStatus,
} from '../../services/api';

const mockSites = [
  { id: 1, customer_id: 1, name: 'Test Site', url: 'https://example.com', is_active: true, last_crawled_at: null, compliance_status: 'pending' as const, created_at: '2025-01-01' },
  { id: 2, customer_id: 1, name: 'Inactive Site', url: 'https://inactive.com', is_active: false, last_crawled_at: null, compliance_status: 'pending' as const, created_at: '2025-01-01' },
];

const mockResult = {
  id: 1,
  site_id: 1,
  site_name: 'Test Site',
  html_data: { prices: { USD: [29.99] }, payment_methods: ['credit_card'], fees: {}, subscription_terms: null, is_complete: true },
  ocr_data: { prices: { USD: [29.99] }, payment_methods: ['credit_card'], fees: {}, subscription_terms: null, is_complete: true },
  discrepancies: [],
  html_violations: [],
  ocr_violations: [],
  screenshot_path: '/tmp/screenshot.png',
  ocr_confidence: 0.95,
  status: 'success',
  error_message: null,
  created_at: '2025-01-01T12:00:00',
};

const renderVerification = () =>
  render(
    <MemoryRouter>
      <Verification />
    </MemoryRouter>
  );

describe('Verification Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (getSites as ReturnType<typeof vi.fn>).mockResolvedValue(mockSites);
  });

  it('renders page header', async () => {
    renderVerification();
    expect(screen.getByText('検証・比較システム')).toBeInTheDocument();
  });

  it('loads and displays only active sites in dropdown', async () => {
    renderVerification();
    await waitFor(() => {
      expect(getSites).toHaveBeenCalled();
    });
    const select = screen.getByLabelText('監視対象サイト:');
    expect(select).toBeInTheDocument();
    // Active site should be present
    expect(screen.getByText('Test Site')).toBeInTheDocument();
    // Inactive site should not be present
    expect(screen.queryByText('Inactive Site')).not.toBeInTheDocument();
  });

  it('disables run button when no site is selected', async () => {
    renderVerification();
    await waitFor(() => expect(getSites).toHaveBeenCalled());

    const button = screen.getByText('検証実行');
    expect(button).toBeDisabled();
  });

  it('disables run button when loading', async () => {
    (triggerVerification as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {})); // never resolves
    (getVerificationStatus as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'processing', result: null });

    renderVerification();
    await waitFor(() => expect(getSites).toHaveBeenCalled());

    // Select a site
    const select = screen.getByLabelText('監視対象サイト:');
    fireEvent.change(select, { target: { value: '1' } });

    const button = screen.getByText('検証実行');
    fireEvent.click(button);

    await waitFor(() => {
      expect(screen.getByText('検証中...')).toBeInTheDocument();
    });
  });

  it('displays comparison table after successful verification', async () => {
    (triggerVerification as ReturnType<typeof vi.fn>).mockResolvedValue({ job_id: 1, status: 'processing', message: 'Started' });
    (getVerificationStatus as ReturnType<typeof vi.fn>).mockResolvedValue({ job_id: 1, status: 'completed', result: mockResult });
    (getVerificationResults as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    renderVerification();
    await waitFor(() => expect(getSites).toHaveBeenCalled());

    // Select site and run
    const select = screen.getByLabelText('監視対象サイト:');
    fireEvent.change(select, { target: { value: '1' } });
    fireEvent.click(screen.getByText('検証実行'));

    await waitFor(() => {
      expect(screen.getByText('検証結果')).toBeInTheDocument();
    }, { timeout: 5000 });
  });

  it('displays error message on verification failure', async () => {
    (triggerVerification as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { data: { detail: 'サーバーエラー' } },
    });

    renderVerification();
    await waitFor(() => expect(getSites).toHaveBeenCalled());

    const select = screen.getByLabelText('監視対象サイト:');
    fireEvent.change(select, { target: { value: '1' } });
    fireEvent.click(screen.getByText('検証実行'));

    await waitFor(() => {
      expect(screen.getByText('サーバーエラー')).toBeInTheDocument();
    });
  });
});
