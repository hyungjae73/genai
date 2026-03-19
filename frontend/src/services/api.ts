import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
const API_KEY = import.meta.env.VITE_API_KEY || 'dev-api-key';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
  },
});

// Types
export interface Site {
  id: number;
  customer_id: number;
  category_id: number | null;
  url: string;
  name: string;
  is_active: boolean;
  last_crawled_at: string | null;
  compliance_status: 'compliant' | 'violation' | 'pending' | 'error';
  created_at: string;
}

export interface Alert {
  id: number;
  site_id: number;
  site_name: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  violation_type: string;
  created_at: string;
  is_resolved: boolean;
}

export interface Statistics {
  total_sites: number;
  active_sites: number;
  total_violations: number;
  high_severity_violations: number;
  success_rate: number;
  last_crawl: string | null;
}

export interface MonitoringHistory {
  id: number;
  site_id: number;
  site_name: string;
  crawled_at: string;
  status: string;
  violations_count: number;
  response_time: number;
}

// API functions
export const getSites = async (): Promise<Site[]> => {
  const response = await api.get('/api/sites/');
  return response.data;
};

export const getSite = async (id: number): Promise<Site> => {
  const response = await api.get(`/api/sites/${id}`);
  return response.data;
};

export const createSite = async (data: {
  customer_id: number;
  name: string;
  url: string;
  monitoring_enabled?: boolean;
}): Promise<Site> => {
  const response = await api.post('/api/sites/', data);
  return response.data;
};

export const updateSite = async (id: number, data: {
  customer_id?: number;
  name?: string;
  url?: string;
  monitoring_enabled?: boolean;
}): Promise<Site> => {
  const response = await api.put(`/api/sites/${id}`, data);
  return response.data;
};

export const deleteSite = async (id: number): Promise<void> => {
  await api.delete(`/api/sites/${id}`);
};

export const getAlerts = async (): Promise<Alert[]> => {
  const response = await api.get('/api/alerts/');
  return response.data;
};

export const getStatistics = async (): Promise<Statistics> => {
  const response = await api.get('/api/monitoring/statistics');
  return response.data;
};

export const getMonitoringHistory = async (): Promise<MonitoringHistory[]> => {
  const response = await api.get('/api/monitoring/history');
  return response.data;
};

export default api;


// Contract Condition Types
export interface ContractCondition {
  id: number;
  site_id: number;
  category_id: number | null;
  version: number;
  is_current: boolean;
  created_at: string;
  prices: {
    [currency: string]: number | number[];
  };
  payment_methods: {
    allowed?: string[];
    required?: string[];
  };
  fees: {
    percentage?: number | number[];
    fixed?: number | number[];
  };
  subscription_terms?: {
    has_commitment?: boolean;
    commitment_months?: number | number[];
    has_cancellation_policy?: boolean;
  };
}

export interface ContractConditionCreate {
  site_id: number;
  prices: {
    [currency: string]: number | number[];
  };
  payment_methods: {
    allowed?: string[];
    required?: string[];
  };
  fees: {
    percentage?: number | number[];
    fixed?: number | number[];
  };
  subscription_terms?: {
    has_commitment?: boolean;
    commitment_months?: number | number[];
    has_cancellation_policy?: boolean;
  };
}

// Customer Types
export interface Customer {
  id: number;
  name: string;
  company_name: string | null;
  email: string;
  phone: string | null;
  address: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerCreate {
  name: string;
  company_name?: string | null;
  email: string;
  phone?: string | null;
  address?: string | null;
  is_active?: boolean;
}

// Customer API functions
export const getCustomers = async (activeOnly: boolean = false): Promise<Customer[]> => {
  const response = await api.get('/api/customers/', {
    params: { active_only: activeOnly }
  });
  return response.data;
};

export const getCustomer = async (id: number): Promise<Customer> => {
  const response = await api.get(`/api/customers/${id}`);
  return response.data;
};

export const createCustomer = async (data: CustomerCreate): Promise<Customer> => {
  const response = await api.post('/api/customers/', data);
  return response.data;
};

export const updateCustomer = async (id: number, data: Partial<CustomerCreate>): Promise<Customer> => {
  const response = await api.put(`/api/customers/${id}`, data);
  return response.data;
};

export const deleteCustomer = async (id: number): Promise<void> => {
  await api.delete(`/api/customers/${id}`);
};

// Screenshot Types
export interface Screenshot {
  id: number;
  site_id: number;
  site_name: string;
  screenshot_type: 'baseline' | 'violation';
  file_path: string;
  file_format: 'png' | 'pdf';
  crawled_at: string;
}

// Screenshot API functions
export const uploadScreenshot = async (
  siteId: number,
  screenshotType: 'baseline' | 'violation',
  file: File
): Promise<Screenshot> => {
  const formData = new FormData();
  formData.append('site_id', siteId.toString());
  formData.append('screenshot_type', screenshotType);
  formData.append('file', file);
  
  const response = await api.post('/api/screenshots/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const captureScreenshot = async (
  siteId: number,
  screenshotType: 'baseline' | 'violation',
  fileFormat: 'png' | 'pdf' = 'png'
): Promise<Screenshot> => {
  const response = await api.post('/api/screenshots/capture', null, {
    params: {
      site_id: siteId,
      screenshot_type: screenshotType,
      file_format: fileFormat,
    },
  });
  return response.data;
};

export const getSiteScreenshots = async (
  siteId: number,
  screenshotType?: 'baseline' | 'violation'
): Promise<Screenshot[]> => {
  const response = await api.get(`/api/screenshots/site/${siteId}`, {
    params: screenshotType ? { screenshot_type: screenshotType } : {}
  });
  return response.data;
};

export const getScreenshotUrl = (screenshotId: number): string => {
  return `${API_BASE_URL}/api/screenshots/view/${screenshotId}`;
};

export const deleteScreenshot = async (screenshotId: number): Promise<void> => {
  await api.delete(`/api/screenshots/${screenshotId}`);
};

// Contract Condition API functions
export const getContracts = async (): Promise<ContractCondition[]> => {
  const response = await api.get('/api/contracts/');
  return response.data;
};

export const getContract = async (id: number): Promise<ContractCondition> => {
  const response = await api.get(`/api/contracts/${id}`);
  return response.data;
};

export const getSiteContracts = async (siteId: number, currentOnly: boolean = false): Promise<ContractCondition[]> => {
  const response = await api.get(`/api/contracts/site/${siteId}`, {
    params: { current_only: currentOnly }
  });
  return response.data;
};

export const createContract = async (data: ContractConditionCreate): Promise<ContractCondition> => {
  const response = await api.post('/api/contracts/', data);
  return response.data;
};

export const updateContract = async (id: number, data: Partial<ContractConditionCreate>): Promise<ContractCondition> => {
  const response = await api.put(`/api/contracts/${id}`, data);
  return response.data;
};

export const deleteContract = async (id: number): Promise<void> => {
  await api.delete(`/api/contracts/${id}`);
};

// Verification Types
export interface VerificationResult {
  id: number;
  site_id: number;
  site_name: string;
  html_data: any;
  ocr_data: any;
  discrepancies: Array<{
    field_name: string;
    html_value: any;
    ocr_value: any;
    difference_type: string;
    severity: string;
  }>;
  html_violations: Array<{
    violation_type: string;
    severity: string;
    field_name: string;
    expected_value: any;
    actual_value: any;
    message: string;
    data_source: string;
  }>;
  ocr_violations: Array<{
    violation_type: string;
    severity: string;
    field_name: string;
    expected_value: any;
    actual_value: any;
    message: string;
    data_source: string;
  }>;
  screenshot_path: string;
  ocr_confidence: number;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface VerificationTriggerRequest {
  site_id: number;
  screenshot_resolution?: [number, number];
  ocr_language?: string;
}

// Verification API functions
export const triggerVerification = async (request: VerificationTriggerRequest): Promise<{
  job_id: number;
  status: string;
  message: string;
}> => {
  const response = await api.post('/api/verification/run', request);
  return response.data;
};

export const getVerificationResults = async (
  siteId: number,
  limit: number = 1,
  offset: number = 0
): Promise<{
  results: VerificationResult[];
  total: number;
  limit: number;
  offset: number;
}> => {
  const response = await api.get(`/api/verification/results/${siteId}`, {
    params: { limit, offset }
  });
  return response.data;
};

export const getVerificationStatus = async (jobId: number): Promise<{
  job_id: number;
  status: string;
  result: VerificationResult | null;
}> => {
  const response = await api.get(`/api/verification/status/${jobId}`);
  return response.data;
};


// Category Types
export interface Category {
  id: number;
  name: string;
  description: string | null;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryCreate {
  name: string;
  description?: string;
  color?: string;
}

// Field Schema Types
export interface FieldSchema {
  id: number;
  category_id: number;
  field_name: string;
  field_type: 'text' | 'number' | 'currency' | 'percentage' | 'date' | 'boolean' | 'list';
  is_required: boolean;
  validation_rules: Record<string, any> | null;
  display_order: number;
  created_at: string;
  updated_at: string;
}

export interface FieldSchemaCreate {
  category_id: number;
  field_name: string;
  field_type: string;
  is_required?: boolean;
  validation_rules?: Record<string, any>;
  display_order?: number;
}

// Extracted Data Types
export interface ExtractedData {
  id: number;
  screenshot_id: number;
  site_id: number;
  extracted_fields: Record<string, any>;
  confidence_scores: Record<string, number>;
  status: 'pending' | 'confirmed' | 'rejected';
  created_at: string;
}

// Field Suggestion Types
export interface FieldSuggestion {
  field_name: string;
  field_type: string;
  sample_value: any;
  confidence: number;
}

// Crawl Types
export interface CrawlJobResponse {
  job_id: string;
  status: string;
}

export interface CrawlStatusResponse {
  job_id: string;
  status: string;
  result?: CrawlResult;
}

export interface CrawlResult {
  id: number;
  site_id: number;
  url: string;
  status_code: number;
  screenshot_path: string | null;
  crawled_at: string;
}

// Category API functions
export const getCategories = async (): Promise<Category[]> => {
  const response = await api.get('/api/categories/');
  return response.data;
};

export const createCategory = async (data: CategoryCreate): Promise<Category> => {
  const response = await api.post('/api/categories/', data);
  return response.data;
};

export const updateCategory = async (id: number, data: Partial<CategoryCreate>): Promise<Category> => {
  const response = await api.put(`/api/categories/${id}`, data);
  return response.data;
};

export const deleteCategory = async (id: number): Promise<void> => {
  await api.delete(`/api/categories/${id}`);
};

// Field Schema API functions
export const getFieldSchemas = async (categoryId: number): Promise<FieldSchema[]> => {
  const response = await api.get(`/api/field-schemas/category/${categoryId}`);
  return response.data;
};

export const createFieldSchema = async (data: FieldSchemaCreate): Promise<FieldSchema> => {
  const response = await api.post('/api/field-schemas/', data);
  return response.data;
};

export const updateFieldSchema = async (id: number, data: Partial<FieldSchemaCreate>): Promise<FieldSchema> => {
  const response = await api.put(`/api/field-schemas/${id}`, data);
  return response.data;
};

export const deleteFieldSchema = async (id: number): Promise<void> => {
  await api.delete(`/api/field-schemas/${id}`);
};

// Data Extraction API functions
export const extractData = async (screenshotId: number): Promise<ExtractedData> => {
  const response = await api.post(`/api/extraction/extract/${screenshotId}`);
  return response.data;
};

export const getExtractedData = async (screenshotId: number): Promise<ExtractedData> => {
  const response = await api.get(`/api/extraction/results/${screenshotId}`);
  return response.data;
};

export const updateExtractedData = async (id: number, data: Partial<ExtractedData>): Promise<ExtractedData> => {
  const response = await api.put(`/api/extraction/results/${id}`, data);
  return response.data;
};

export const suggestFields = async (screenshotId: number): Promise<FieldSuggestion[]> => {
  const response = await api.post(`/api/extraction/suggest-fields/${screenshotId}`);
  return response.data;
};

// Site Alerts API function
export const getSiteAlerts = async (siteId: number, isResolved?: boolean): Promise<Alert[]> => {
  const response = await api.get(`/api/alerts/site/${siteId}`, {
    params: isResolved !== undefined ? { is_resolved: isResolved } : {}
  });
  return response.data;
};

// Crawl API functions
export const triggerCrawl = async (siteId: number): Promise<CrawlJobResponse> => {
  const response = await api.post(`/api/crawl/site/${siteId}`);
  return response.data;
};

export const getCrawlStatus = async (jobId: string): Promise<CrawlStatusResponse> => {
  const response = await api.get(`/api/crawl/status/${jobId}`);
  return response.data;
};

export const getCrawlResults = async (siteId: number): Promise<CrawlResult[]> => {
  const response = await api.get(`/api/crawl/results/${siteId}`);
  return response.data;
};

export const getLatestCrawlResult = async (siteId: number): Promise<CrawlResult> => {
  const response = await api.get(`/api/crawl/results/${siteId}/latest`);
  return response.data;
};
