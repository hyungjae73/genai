/**
 * 審査ワークフロー関連の TypeScript 型定義
 * 要件: 1.1, 5.1, 8.2
 */

export type ReviewStatus = 'pending' | 'in_review' | 'approved' | 'rejected' | 'escalated';
export type ReviewPriority = 'critical' | 'high' | 'medium' | 'low';
export type ReviewType = 'violation' | 'dark_pattern' | 'fake_site';
export type ReviewStage = 'primary' | 'secondary';
export type ReviewDecisionType = 'approved' | 'rejected' | 'escalated';

export interface ReviewItem {
  id: number;
  alert_id: number | null;
  site_id: number;
  review_type: ReviewType;
  status: ReviewStatus;
  priority: ReviewPriority;
  assigned_to: number | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewDecision {
  id: number;
  review_item_id: number;
  reviewer_id: number;
  decision: ReviewDecisionType;
  comment: string;
  review_stage: ReviewStage;
  decided_at: string;
}

export interface AlertDetailInReview {
  id: number;
  severity: string;
  message: string;
  alert_type: string;
  created_at: string;
  fake_domain?: string | null;
  domain_similarity_score?: number | null;
  content_similarity_score?: number | null;
}

export interface ViolationDetailInReview {
  id: number;
  violation_type: string;
  expected_value: Record<string, unknown>;
  actual_value: Record<string, unknown>;
}

export interface DarkPatternDetailInReview {
  dark_pattern_score: number | null;
  dark_pattern_types: Record<string, unknown> | null;
}

export interface FakeSiteDetailInReview {
  fake_domain: string | null;
  domain_similarity_score: number | null;
  content_similarity_score: number | null;
}

export interface SiteBasicInfo {
  id: number;
  name: string;
  url: string;
}

export interface ReviewDetail {
  review_item: ReviewItem;
  alert: AlertDetailInReview | null;
  violation: ViolationDetailInReview | null;
  dark_pattern: DarkPatternDetailInReview | null;
  fake_site: FakeSiteDetailInReview | null;
  site: SiteBasicInfo | null;
  decisions: ReviewDecision[];
}

export interface PaginatedReviewResponse {
  items: ReviewItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewStats {
  by_status: Record<ReviewStatus, number>;
  by_priority: Record<ReviewPriority, number>;
  by_review_type: Record<ReviewType, number>;
}

export interface ReviewDecisionRequest {
  decision: ReviewDecisionType;
  comment: string;
}

export interface AssignReviewerRequest {
  reviewer_id: number;
}
