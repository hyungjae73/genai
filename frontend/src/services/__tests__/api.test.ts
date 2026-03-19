import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import {
  triggerVerification,
  getVerificationResults,
  getVerificationStatus,
} from '../api';

vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    defaults: { headers: { common: {} } },
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

const mockedAxios = axios as any;

describe('Verification API Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('triggerVerification', () => {
    it('sends POST request with site_id', async () => {
      const mockResponse = { data: { job_id: 1, status: 'processing', message: 'Started' } };
      mockedAxios.post.mockResolvedValue(mockResponse);

      const result = await triggerVerification({ site_id: 42 });

      expect(mockedAxios.post).toHaveBeenCalledWith('/api/verification/run', { site_id: 42 });
      expect(result).toEqual(mockResponse.data);
    });

    it('sends optional parameters', async () => {
      const mockResponse = { data: { job_id: 1, status: 'processing', message: 'Started' } };
      mockedAxios.post.mockResolvedValue(mockResponse);

      await triggerVerification({ site_id: 42, ocr_language: 'jpn' });

      expect(mockedAxios.post).toHaveBeenCalledWith('/api/verification/run', {
        site_id: 42,
        ocr_language: 'jpn',
      });
    });

    it('propagates errors', async () => {
      mockedAxios.post.mockRejectedValue(new Error('Network Error'));

      await expect(triggerVerification({ site_id: 42 })).rejects.toThrow('Network Error');
    });
  });

  describe('getVerificationResults', () => {
    it('sends GET request with site_id and pagination', async () => {
      const mockResponse = { data: { results: [], total: 0, limit: 10, offset: 0 } };
      mockedAxios.get.mockResolvedValue(mockResponse);

      const result = await getVerificationResults(42, 10, 0);

      expect(mockedAxios.get).toHaveBeenCalledWith('/api/verification/results/42', {
        params: { limit: 10, offset: 0 },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('uses default pagination values', async () => {
      const mockResponse = { data: { results: [], total: 0, limit: 1, offset: 0 } };
      mockedAxios.get.mockResolvedValue(mockResponse);

      await getVerificationResults(42);

      expect(mockedAxios.get).toHaveBeenCalledWith('/api/verification/results/42', {
        params: { limit: 1, offset: 0 },
      });
    });

    it('propagates errors', async () => {
      mockedAxios.get.mockRejectedValue(new Error('Not Found'));

      await expect(getVerificationResults(99999)).rejects.toThrow('Not Found');
    });
  });

  describe('getVerificationStatus', () => {
    it('sends GET request with job_id', async () => {
      const mockResponse = { data: { job_id: 1, status: 'completed', result: null } };
      mockedAxios.get.mockResolvedValue(mockResponse);

      const result = await getVerificationStatus(1);

      expect(mockedAxios.get).toHaveBeenCalledWith('/api/verification/status/1');
      expect(result).toEqual(mockResponse.data);
    });

    it('propagates errors', async () => {
      mockedAxios.get.mockRejectedValue(new Error('Server Error'));

      await expect(getVerificationStatus(1)).rejects.toThrow('Server Error');
    });
  });
});
