# Spec Dependencies Map

This document tracks dependencies between specs and their impact on shared resources (database, API, frontend components).

## Spec Registry

| Spec ID | Feature Name | Status | DB Changes | Frontend Changes | Backend API Changes |
|---------|-------------|--------|------------|-----------------|-------------------|
| crawl-data-enhancement | クロールデータ拡張 | completed | extracted_payment_info.source column, crawl_jobs table | CrawlResultReview, CrawlResultComparison | extracted_data API, crawl API |
| docker-cicd-pipeline | Docker CI/CD | completed | none | none | health endpoint, Dockerfiles |
| fake-site-detection-alert | 偽サイト検知アラート | completed | alerts.fake_domain, alerts.legitimate_domain, alerts.domain_similarity_score, alerts.content_similarity_score | FakeSites page, Alerts page | alerts API |
| figma-ux-improvement | Figma UX改善 | completed | none | All pages (design system), tokens, components | none |
| screenshot-integration-rename | スクリーンショット統合・リネーム | in-progress | none (frontend only) | HierarchyView→SiteManagement, Screenshots integration, Verification integration, Sidebar, Help modals | none |
| crawl-pipeline-architecture | クロールパイプラインアーキテクチャ | completed | MonitoringSite: 5 new columns (pre_capture_script, crawl_priority, etag, last_modified_header, plugin_config), VerificationResult: 5 new columns (structured_data, structured_data_violations, data_source, structured_data_status, evidence_status), EvidenceRecord table (new), CrawlSchedule table (new) | ScheduleTab (5th tab in SiteDetailPanel) | schedule CRUD API (/api/sites/{id}/schedule), site settings update (pre_capture_script, plugin_config validation) |
| testcontainers-migration | テストインフラPostgreSQL移行 | in-progress | JSON→JSONB migration (4 fields), Alembic: k6l7m8n9o0p1 | none | none (test infrastructure only) |
| dark-pattern-notification | ダークパターン通知 | in-progress | notification_records table (new), Alembic: m8n9o0p1q2r3 | none | notification config API, notification history API |
| stealth-browser-hardening | ステルスブラウザ強化 | completed | MonitoringSite.is_hard_target column, Alembic: n9o0p1q2r3s4 | none | GET /api/monitoring/sites/{site_id}/fetch-telemetry |
| advanced-dark-pattern-detection | 高度ダークパターン検出 | in-progress | MonitoringSite.merchant_category, VerificationResult: dark_pattern_score/subscores/types, Violation.dark_pattern_category, dynamic_compliance_rules table, content_fingerprints table, Alembic: o0p1q2r3s4t5 | none | GET /api/sites/{id}/dark-patterns, GET /api/sites/{id}/dark-patterns/history |
| user-auth-rbac | ユーザ管理・権限管理 | in-progress | users table (new) + must_change_password column, Alembic: q1r2s3t4u5v6 | Login page, AuthContext, ProtectedRoute, AppLayout (role-based nav), ChangePassword page, ユーザ管理 placeholder | POST /api/auth/login, POST /api/auth/refresh, POST /api/auth/logout, GET /api/auth/me, POST /api/auth/change-password, CRUD /api/users, POST /api/users/{id}/reset-password, 全既存16ルーターに認証Depends追加 |
| manual-review-workflow | 手動審査ワークフロー | completed | review_items table (new), review_decisions table (new), Alembic: p1q2r3s4t5u6 | Reviews page, ReviewDetail page, ReviewDashboard page, AppLayout (審査グループ追加), App.tsx (3ルート追加), types/review.ts, api.ts (8関数追加) | GET/POST /api/reviews, GET /api/reviews/{id}, POST /api/reviews/{id}/assign, POST /api/reviews/{id}/decide, POST /api/reviews/{id}/final-decide, GET /api/reviews/escalated, GET /api/reviews/stats, GET /api/reviews/{id}/decisions |
| verification-flow-restructure | 検証フロー再構築 | completed | なし（DB変更は crawl-pipeline-architecture で実装済み） | なし | schemas.py に EvidenceRecordResponse 追加、verification.py の _format_verification_result に evidence_records フィールド追加 |
| crawl-modal-automation | クロールモーダル自動化 | completed | なし（pre_capture_script カラムは crawl-pipeline-architecture で実装済み） | ScheduleTab (PreCaptureScript editor) — crawl-pipeline-architecture で実装済み | なし |
| dynamic-contract-form | 契約条件動的フォーム | completed | なし（ContractCondition.category_id は既存カラム、dynamic_fields は既存 JSONB フィールドを活用） | DynamicFieldInput コンポーネント（新規）、validateDynamicField ユーティリティ（新規）、Contracts.tsx（動的フォーム化）、Categories.tsx（FieldSchemaManager 統合） | schemas.py: ContractConditionCreate/Update/Response に dynamic_fields・category_id 追加 |

## Database Migration Chain

```
55d4c7aa85ce (initial schema)
  └── fdc38e236687 (customer and screenshot)
      └── c7f1f5cab04d (categories, field_schemas, extracted_data)
          └── d8a9b2c3e4f5 (extracted_payment_info table)
              └── e5f6g7h8i9j0 (screenshot_path to crawl_results)
                  └── f1g2h3i4j5k6 (price_history table)
                      └── g2h3i4j5k6l7 (price change columns to alerts)
                          └── h3i4j5k6l7m8 (crawl_jobs, source field)
                              └── i4j5k6l7m8n9 (fake site columns to alerts) ← CURRENT HEAD
                                  └── 0340f3c9d609 (verification_results table)
                                      └── j5k6l7m8n9o0 (crawl pipeline: MonitoringSite/VerificationResult columns, EvidenceRecord, CrawlSchedule tables)
                                          └── k6l7m8n9o0p1 (JSON→JSONB: pre_capture_script, plugin_config, structured_data, structured_data_violations)
                                              └── l7m8n9o0p1q2 (scraping_tasks table)
                                                  └── m8n9o0p1q2r3 (notification_records table)
                                      └── n9o0p1q2r3s4 (is_hard_target column on monitoring_sites)
                                          └── o0p1q2r3s4t5 (dark pattern columns: merchant_category, dark_pattern_score/subscores/types, dark_pattern_category, dynamic_compliance_rules table, content_fingerprints table)
                                              └── q1r2s3t4u5v6 (users table)
                                                  └── p1q2r3s4t5u6 (review_items table, review_decisions table) ← CURRENT HEAD
```

## Dependency Graph

```
crawl-data-enhancement
  ├── DB: extracted_payment_info.source, crawl_jobs table
  ├── depends on: initial schema (monitoring_sites, crawl_results)
  └── depended by: figma-ux-improvement (CrawlResultReview refactoring)

fake-site-detection-alert
  ├── DB: alerts table columns (fake_domain, etc.)
  ├── depends on: initial schema (alerts table)
  └── depended by: figma-ux-improvement (FakeSites/Alerts page refactoring)

figma-ux-improvement
  ├── DB: none
  ├── depends on: crawl-data-enhancement (CrawlResultReview component), fake-site-detection-alert (FakeSites/Alerts pages)
  └── depended by: screenshot-integration-rename (design system components)

screenshot-integration-rename
  ├── DB: none (frontend only)
  ├── depends on: figma-ux-improvement (UI components, design tokens)
  └── depended by: (none yet)

docker-cicd-pipeline
  ├── DB: none
  ├── depends on: none
  └── depended by: none

crawl-pipeline-architecture
  ├── DB: MonitoringSite columns, VerificationResult columns, EvidenceRecord table, CrawlSchedule table
  ├── depends on: initial schema (monitoring_sites, verification_results, alerts), crawl-modal-automation (superseded), verification-flow-restructure (superseded)
  └── depended by: testcontainers-migration (JSON→JSONB migration for columns added here)

testcontainers-migration
  ├── DB: JSON→JSONB type change (4 fields), conftest.py rewrite (all test files affected)
  ├── depends on: crawl-pipeline-architecture (pre_capture_script, plugin_config columns)
  └── depended by: (none yet)

dark-pattern-notification
  ├── DB: notification_records table
  ├── depends on: initial schema (monitoring_sites, alerts), crawl-pipeline-architecture (CrawlPlugin, plugin_config)
  └── depended by: (none yet)

stealth-browser-hardening
  ├── DB: MonitoringSite.is_hard_target column
  ├── depends on: crawl-pipeline-architecture (BrowserPool, PageFetcherStage, CrawlPlugin, StealthBrowserFactory, ScrapingConfig)
  └── depended by: (none yet)

manual-review-workflow
  ├── DB: review_items table, review_decisions table (Alembic: p1q2r3s4t5u6)
  ├── Backend: src/review/state_machine.py, src/review/service.py, src/api/reviews.py, schemas.py (審査スキーマ), main.py (/api/reviews 登録)
  ├── Frontend: Reviews.tsx, ReviewDetail.tsx, ReviewDashboard.tsx, types/review.ts, api.ts, App.tsx, AppLayout.tsx
  ├── Hooks: alert_plugin.py (Alert作成→enqueue_from_alert), db_storage_plugin.py (dark_pattern_score>=0.7→enqueue_from_dark_pattern), tasks.py (fake_site→enqueue_from_alert)
  ├── depends on: user-auth-rbac (reviewer/admin ロール, require_role dependency), initial schema (alerts, monitoring_sites, violations, verification_results)
  └── depended by: (none yet)
```

## Rules for Maintaining This Document

1. When creating a new spec, add it to the Spec Registry table
2. When a spec modifies `models.py`, record the DB changes and ensure a migration is created
3. When a spec depends on another spec's output, record the dependency
4. Update the Migration Chain when new migrations are added
5. Update Status when specs are completed
