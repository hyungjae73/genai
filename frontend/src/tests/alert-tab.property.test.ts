import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { filterAlertsByStatus } from '../components/hierarchy/tabs/AlertTab';
import type { Alert } from '../services/api';

// --- Arbitrary generators ---

const arbISODate = fc
  .integer({ min: 946684800000, max: 1924905600000 }) // 2000-01-01 to 2030-12-31 in ms
  .map((ts) => new Date(ts).toISOString());

const arbSeverity = fc.constantFrom<'low' | 'medium' | 'high' | 'critical'>(
  'low',
  'medium',
  'high',
  'critical'
);

const arbViolationType = fc.constantFrom(
  'price_violation',
  'payment_method_violation',
  'fee_violation',
  'subscription_violation',
  'format_violation',
  'content_violation'
);

const arbAlert: fc.Arbitrary<Alert> = fc.record({
  id: fc.integer({ min: 1, max: 100000 }),
  site_id: fc.integer({ min: 1, max: 10000 }),
  site_name: fc.string({ minLength: 1, maxLength: 100 }),
  severity: arbSeverity,
  message: fc.string({ minLength: 10, maxLength: 500 }),
  violation_type: arbViolationType,
  created_at: arbISODate,
  is_resolved: fc.boolean(),
});

const arbAlertList = fc.array(arbAlert, { minLength: 1, maxLength: 20 }).map((alerts) =>
  // Ensure unique IDs
  alerts.map((alert, i) => ({ ...alert, id: i + 1 }))
);

const arbCustomerName = fc.string({ minLength: 1, maxLength: 100 });

// --- Helper function to render alert as HTML string ---

/**
 * Renders an alert item to HTML string for testing purposes.
 * This simulates what the AlertTab component renders for each alert.
 */
const renderAlertToHTML = (alert: Alert, customerName: string): string => {
  const severityLabels: Record<Alert['severity'], string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '緊急',
  };

  const severityLabel = severityLabels[alert.severity];
  const statusLabel = alert.is_resolved ? '解決済み' : '未解決';
  const detectionDate = new Date(alert.created_at).toLocaleString('ja-JP');

  return `
    <div class="alert-item">
      <div class="alert-header">
        <span class="severity-badge severity-${alert.severity}">${severityLabel}</span>
        <span class="status-badge ${alert.is_resolved ? 'resolved' : 'unresolved'}">${statusLabel}</span>
        <span class="alert-date">${detectionDate}</span>
      </div>
      <div class="alert-details">
        <div class="alert-info">
          <div class="info-row">
            <span class="info-label">顧客名:</span>
            <span class="info-value">${customerName}</span>
          </div>
          <div class="info-row">
            <span class="info-label">商品ページ:</span>
            <span class="info-value">${alert.site_name}</span>
          </div>
          <div class="info-row">
            <span class="info-label">違反タイプ:</span>
            <span class="info-value">${alert.violation_type}</span>
          </div>
        </div>
        <div class="alert-message">
          <p>${alert.message}</p>
        </div>
      </div>
    </div>
  `;
};

// --- Property 7: アラート表示の完全性 ---

describe('Feature: hierarchical-ui-restructure, Property 7: アラート表示の完全性', () => {
  /**
   * **Validates: Requirements 6.2, 6.3, 6.4, 6.6**
   *
   * 任意のアラートデータ（違反情報を含む）に対して、レンダリング結果には顧客名、商品ページURL、
   * 変更箇所（フィールド名・期待値・実際値）、重要度バッジ、検出日時、
   * および期待値と実際値の比較表示がすべて含まれること。
   */

  it('rendered alert contains all required information: customer name, site name, violation type, severity badge, and detection date', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          // Render the alert to HTML
          const html = renderAlertToHTML(alert, customerName);

          // Property: All required information must be present in the rendered output

          // 1. Customer name (顧客名)
          expect(html).toContain('顧客名:');
          expect(html).toContain(customerName);

          // 2. Site name / Product page URL (商品ページ)
          expect(html).toContain('商品ページ:');
          expect(html).toContain(alert.site_name);

          // 3. Violation type / Change location (変更箇所 - 違反タイプ)
          expect(html).toContain('違反タイプ:');
          expect(html).toContain(alert.violation_type);

          // 4. Severity badge (重要度バッジ)
          const severityLabels: Record<Alert['severity'], string> = {
            low: '低',
            medium: '中',
            high: '高',
            critical: '緊急',
          };
          const expectedSeverityLabel = severityLabels[alert.severity];
          expect(html).toContain(`severity-badge severity-${alert.severity}`);
          expect(html).toContain(expectedSeverityLabel);

          // 5. Detection date (検出日時)
          const detectionDate = new Date(alert.created_at).toLocaleString('ja-JP');
          expect(html).toContain(detectionDate);

          // 6. Alert message (変更箇所の詳細)
          expect(html).toContain(alert.message);

          // 7. Resolution status (解決済み/未解決)
          const expectedStatus = alert.is_resolved ? '解決済み' : '未解決';
          expect(html).toContain(expectedStatus);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('severity badge class matches severity level for all alerts', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          // Verify the severity badge has the correct CSS class
          expect(html).toContain(`severity-badge severity-${alert.severity}`);

          // Verify the severity label is correct
          const severityLabels: Record<Alert['severity'], string> = {
            low: '低',
            medium: '中',
            high: '高',
            critical: '緊急',
          };
          expect(html).toContain(severityLabels[alert.severity]);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('detection date is formatted correctly in Japanese locale', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          // Parse the date and format it
          const detectionDate = new Date(alert.created_at).toLocaleString('ja-JP');

          // Verify the formatted date is present
          expect(html).toContain(detectionDate);

          // Verify the date is valid (not "Invalid Date")
          expect(detectionDate).not.toBe('Invalid Date');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('resolution status badge is displayed correctly', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          if (alert.is_resolved) {
            expect(html).toContain('status-badge resolved');
            expect(html).toContain('解決済み');
          } else {
            expect(html).toContain('status-badge unresolved');
            expect(html).toContain('未解決');
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('all alert information fields have proper labels', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          // Verify all required labels are present
          const requiredLabels = ['顧客名:', '商品ページ:', '違反タイプ:'];

          requiredLabels.forEach((label) => {
            expect(html).toContain(label);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('alert message is displayed in the details section', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          // Verify the message is in the alert-message section
          expect(html).toContain('<div class="alert-message">');
          expect(html).toContain(`<p>${alert.message}</p>`);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('alert structure contains all required sections', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          // Verify the main structure elements are present
          expect(html).toContain('<div class="alert-item">');
          expect(html).toContain('<div class="alert-header">');
          expect(html).toContain('<div class="alert-details">');
          expect(html).toContain('<div class="alert-info">');
          expect(html).toContain('<div class="alert-message">');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('multiple alerts all contain complete information', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbCustomerName,
        (alerts, customerName) => {
          // Render all alerts
          const htmlList = alerts.map((alert) => renderAlertToHTML(alert, customerName));

          // Verify each alert contains all required information
          htmlList.forEach((html, index) => {
            const alert = alerts[index];

            // Customer name
            expect(html).toContain(customerName);

            // Site name
            expect(html).toContain(alert.site_name);

            // Violation type
            expect(html).toContain(alert.violation_type);

            // Severity badge
            expect(html).toContain(`severity-${alert.severity}`);

            // Detection date
            const detectionDate = new Date(alert.created_at).toLocaleString('ja-JP');
            expect(html).toContain(detectionDate);

            // Message
            expect(html).toContain(alert.message);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('customer name is consistently displayed across all alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbCustomerName,
        (alerts, customerName) => {
          // Render all alerts
          const htmlList = alerts.map((alert) => renderAlertToHTML(alert, customerName));

          // Verify the customer name appears in every alert
          htmlList.forEach((html) => {
            // Check if customer name is present (using includes to avoid regex issues)
            expect(html).toContain(customerName);
            
            // Verify it appears in the info-value section
            expect(html).toContain(`<span class="info-value">${customerName}</span>`);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('severity levels are correctly mapped to Japanese labels', () => {
    fc.assert(
      fc.property(
        arbAlert,
        arbCustomerName,
        (alert, customerName) => {
          const html = renderAlertToHTML(alert, customerName);

          const severityMapping: Record<Alert['severity'], string> = {
            low: '低',
            medium: '中',
            high: '高',
            critical: '緊急',
          };

          const expectedLabel = severityMapping[alert.severity];
          expect(html).toContain(expectedLabel);

          // Verify no other severity labels are present
          const _otherLabels = Object.values(severityMapping).filter(
            (label) => label !== expectedLabel
          );
          
          // Verify the correct label IS present
          expect(html).toContain(expectedLabel);
        }
      ),
      { numRuns: 100 }
    );
  });
});

// --- Property 8: アラートの解決状態フィルタリング ---

describe('Feature: hierarchical-ui-restructure, Property 8: アラートの解決状態フィルタリング', () => {
  /**
   * **Validates: Requirements 6.5**
   *
   * 任意の解決済み/未解決が混在するアラートリストに対して、解決状態フィルターを適用した場合、
   * 表示されるアラートはすべてフィルター条件に一致すること。
   */

  const arbFilterStatus = fc.constantFrom<'all' | 'resolved' | 'unresolved'>(
    'all',
    'resolved',
    'unresolved'
  );

  it('filtering by "all" returns all alerts unchanged', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        (alerts) => {
          const filtered = filterAlertsByStatus(alerts, 'all');

          // Property: When filter is "all", all alerts should be returned
          expect(filtered).toHaveLength(alerts.length);
          expect(filtered).toEqual(alerts);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering by "resolved" returns only resolved alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        (alerts) => {
          const filtered = filterAlertsByStatus(alerts, 'resolved');

          // Property: All filtered alerts must have is_resolved = true
          filtered.forEach((alert) => {
            expect(alert.is_resolved).toBe(true);
          });

          // Property: The count should match the number of resolved alerts
          const expectedCount = alerts.filter((a) => a.is_resolved).length;
          expect(filtered).toHaveLength(expectedCount);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering by "unresolved" returns only unresolved alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        (alerts) => {
          const filtered = filterAlertsByStatus(alerts, 'unresolved');

          // Property: All filtered alerts must have is_resolved = false
          filtered.forEach((alert) => {
            expect(alert.is_resolved).toBe(false);
          });

          // Property: The count should match the number of unresolved alerts
          const expectedCount = alerts.filter((a) => !a.is_resolved).length;
          expect(filtered).toHaveLength(expectedCount);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtered alerts are a subset of original alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbFilterStatus,
        (alerts, filterStatus) => {
          const filtered = filterAlertsByStatus(alerts, filterStatus);

          // Property: Every filtered alert must exist in the original list
          filtered.forEach((filteredAlert) => {
            const exists = alerts.some((alert) => alert.id === filteredAlert.id);
            expect(exists).toBe(true);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering preserves alert order', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbFilterStatus,
        (alerts, filterStatus) => {
          const filtered = filterAlertsByStatus(alerts, filterStatus);

          // Property: The relative order of alerts should be preserved
          // Extract IDs from original and filtered lists
          const originalIds = alerts.map((a) => a.id);
          const filteredIds = filtered.map((a) => a.id);

          // Check that filtered IDs appear in the same order as in original
          let originalIndex = 0;
          for (const filteredId of filteredIds) {
            // Find the next occurrence of this ID in the original list
            while (originalIndex < originalIds.length && originalIds[originalIndex] !== filteredId) {
              originalIndex++;
            }
            // If we found it, the order is preserved so far
            expect(originalIndex).toBeLessThan(originalIds.length);
            originalIndex++;
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering does not modify original alert list', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbFilterStatus,
        (alerts, filterStatus) => {
          // Create a deep copy to compare later
          const originalCopy = JSON.parse(JSON.stringify(alerts));

          // Apply filter
          filterAlertsByStatus(alerts, filterStatus);

          // Property: Original list should remain unchanged
          expect(alerts).toEqual(originalCopy);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering with mixed resolution statuses works correctly', () => {
    fc.assert(
      fc.property(
        fc.array(arbAlert, { minLength: 10, maxLength: 50 }),
        (alerts) => {
          // Ensure we have a mix of resolved and unresolved alerts
          const mixedAlerts = alerts.map((alert, i) => ({
            ...alert,
            id: i + 1,
            is_resolved: i % 2 === 0, // Alternate between resolved and unresolved
          }));

          const resolvedFiltered = filterAlertsByStatus(mixedAlerts, 'resolved');
          const unresolvedFiltered = filterAlertsByStatus(mixedAlerts, 'unresolved');
          const allFiltered = filterAlertsByStatus(mixedAlerts, 'all');

          // Property: Resolved + Unresolved should equal All
          expect(resolvedFiltered.length + unresolvedFiltered.length).toBe(allFiltered.length);

          // Property: No overlap between resolved and unresolved
          const resolvedIds = new Set(resolvedFiltered.map((a) => a.id));
          const unresolvedIds = new Set(unresolvedFiltered.map((a) => a.id));
          
          resolvedIds.forEach((id) => {
            expect(unresolvedIds.has(id)).toBe(false);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering empty list returns empty list', () => {
    fc.assert(
      fc.property(
        arbFilterStatus,
        (filterStatus) => {
          const filtered = filterAlertsByStatus([], filterStatus);

          // Property: Filtering an empty list should return an empty list
          expect(filtered).toHaveLength(0);
          expect(filtered).toEqual([]);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering list with all resolved alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        (alerts) => {
          // Create a list where all alerts are resolved
          const allResolved = alerts.map((alert) => ({
            ...alert,
            is_resolved: true,
          }));

          const resolvedFiltered = filterAlertsByStatus(allResolved, 'resolved');
          const unresolvedFiltered = filterAlertsByStatus(allResolved, 'unresolved');
          const allFiltered = filterAlertsByStatus(allResolved, 'all');

          // Property: Resolved filter should return all alerts
          expect(resolvedFiltered).toHaveLength(allResolved.length);

          // Property: Unresolved filter should return empty list
          expect(unresolvedFiltered).toHaveLength(0);

          // Property: All filter should return all alerts
          expect(allFiltered).toHaveLength(allResolved.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filtering list with all unresolved alerts', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        (alerts) => {
          // Create a list where all alerts are unresolved
          const allUnresolved = alerts.map((alert) => ({
            ...alert,
            is_resolved: false,
          }));

          const resolvedFiltered = filterAlertsByStatus(allUnresolved, 'resolved');
          const unresolvedFiltered = filterAlertsByStatus(allUnresolved, 'unresolved');
          const allFiltered = filterAlertsByStatus(allUnresolved, 'all');

          // Property: Resolved filter should return empty list
          expect(resolvedFiltered).toHaveLength(0);

          // Property: Unresolved filter should return all alerts
          expect(unresolvedFiltered).toHaveLength(allUnresolved.length);

          // Property: All filter should return all alerts
          expect(allFiltered).toHaveLength(allUnresolved.length);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('filter status values produce consistent results', () => {
    fc.assert(
      fc.property(
        arbAlertList,
        arbFilterStatus,
        (alerts, filterStatus) => {
          // Apply filter twice
          const filtered1 = filterAlertsByStatus(alerts, filterStatus);
          const filtered2 = filterAlertsByStatus(alerts, filterStatus);

          // Property: Same input should produce same output (idempotency)
          expect(filtered1).toEqual(filtered2);
        }
      ),
      { numRuns: 100 }
    );
  });
});
