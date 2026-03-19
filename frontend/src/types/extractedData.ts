/**
 * Type definitions for extracted payment information.
 *
 * Maps to the backend ExtractedPaymentInfo and PriceHistory models
 * and their corresponding API response schemas.
 */

// --- Sub-object types ---

export interface ProductInfo {
  name?: string;
  description?: string;
  sku?: string;
  category?: string;
  brand?: string;
}

export interface PriceInfo {
  amount: number;
  currency: string;
  price_type?: string;
  condition?: string;
  tax_included?: boolean;
}

export interface PaymentMethod {
  method_name: string;
  provider?: string | null;
  processing_fee?: number;
  fee_type?: string;
}

export interface Fee {
  fee_type: string;
  amount: number;
  currency: string;
  description?: string;
  condition?: string;
}

/** Per-field confidence scores keyed by field name. */
export type ConfidenceScores = Record<string, number>;

// --- Main response types ---

export interface ExtractedPaymentInfo {
  id: number;
  crawl_result_id: number;
  site_id: number;
  product_info: ProductInfo | null;
  price_info: PriceInfo[] | null;
  payment_methods: PaymentMethod[] | null;
  fees: Fee[] | null;
  metadata: Record<string, unknown> | null;
  confidence_scores: ConfidenceScores | null;
  overall_confidence_score: number | null;
  status: 'pending' | 'approved' | 'rejected' | 'failed';
  language: string | null;
  extracted_at: string;
}

export interface PaginatedExtractedPaymentInfo {
  items: ExtractedPaymentInfo[];
  total: number;
  page: number;
  page_size: number;
}

/** Payload accepted by PUT /api/extracted-data/{id}. */
export interface ExtractedPaymentInfoUpdate {
  product_info?: ProductInfo;
  price_info?: PriceInfo[];
  payment_methods?: PaymentMethod[];
  fees?: Fee[];
  status?: 'pending' | 'approved' | 'rejected';
}

// --- Price history types ---

export interface PriceHistory {
  id: number;
  site_id: number;
  product_identifier: string;
  price: number;
  currency: string;
  price_type: string;
  previous_price: number | null;
  price_change_amount: number | null;
  price_change_percentage: number | null;
  recorded_at: string;
}

export interface PriceHistoryList {
  items: PriceHistory[];
  total: number;
}

// --- Audit log types ---

export interface AuditLogEntry {
  id: number;
  user: string;
  timestamp: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  action: string;
}
