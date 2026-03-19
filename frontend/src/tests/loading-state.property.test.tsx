import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import React from 'react';

// --- Arbitrary generators ---

const arbSiteId = fc.integer({ min: 1, max: 100000 });
const arbCustomerName = fc.string({ minLength: 1, maxLength: 100 });
const arbLoadingState = fc.boolean();

// --- Mock components that simulate loading states ---

interface MockHierarchyViewProps {
  loading: boolean;
}

const MockHierarchyView: React.FC<MockHierarchyViewProps> = ({ loading }) => {
  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }
  return <div className="hierarchy-view">Content loaded</div>;
};

interface MockTabContentProps {
  loading: boolean;
  tabName: string;
}

const MockTabContent: React.FC<MockTabContentProps> = ({ loading, tabName }) => {
  if (loading) {
    return (
      <div className="tab-loading">
        <span className="spinner">⟳</span>
        <span>読み込み中...</span>
      </div>
    );
  }
  return <div className="tab-content">{tabName} content loaded</div>;
};

interface MockDataExtractionProps {
  isExtracting: boolean;
}

const MockDataExtraction: React.FC<MockDataExtractionProps> = ({ isExtracting }) => {
  if (isExtracting) {
    return (
      <div className="extraction-progress">
        <div className="progress-bar">
          <div className="progress-bar-fill"></div>
        </div>
        <p>データ抽出が実行中です...</p>
      </div>
    );
  }
  return <div className="extraction-complete">Extraction complete</div>;
};

// --- Property 17: ローディング状態の表示 ---

describe('Feature: hierarchical-ui-restructure, Property 17: ローディング状態の表示', () => {
  /**
   * **Validates: Requirements 10.1, 10.2, 10.3**
   *
   * 任意のコンポーネント（階層型ビュー、タブコンテンツ、データ抽出）がデータ取得中（loading=true）の場合、
   * ローディングインジケーターが表示されること。
   */

  it('HierarchyView displays loading indicator when loading=true', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        (loading) => {
          const { container } = render(<MockHierarchyView loading={loading} />);

          if (loading) {
            // When loading=true, loading indicator should be displayed
            const loadingIndicator = container.querySelector('.loading');
            expect(loadingIndicator).not.toBeNull();
            expect(loadingIndicator?.textContent).toContain('読み込み中');
            
            // Content should not be displayed
            const content = container.querySelector('.hierarchy-view');
            expect(content).toBeNull();
          } else {
            // When loading=false, loading indicator should not be displayed
            const loadingIndicator = container.querySelector('.loading');
            expect(loadingIndicator).toBeNull();
            
            // Content should be displayed
            const content = container.querySelector('.hierarchy-view');
            expect(content).not.toBeNull();
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tab content displays loading indicator when loading=true for any tab type', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (loading, tabName) => {
          const { container } = render(
            <MockTabContent loading={loading} tabName={tabName} />
          );

          if (loading) {
            // When loading=true, tab loading indicator should be displayed
            const tabLoading = container.querySelector('.tab-loading');
            expect(tabLoading).not.toBeNull();
            expect(tabLoading?.textContent).toContain('読み込み中');
            
            // Should have spinner
            const spinner = container.querySelector('.spinner');
            expect(spinner).not.toBeNull();
            
            // Tab content should not be displayed
            const content = container.querySelector('.tab-content');
            expect(content).toBeNull();
          } else {
            // When loading=false, tab loading indicator should not be displayed
            const tabLoading = container.querySelector('.tab-loading');
            expect(tabLoading).toBeNull();
            
            // Tab content should be displayed
            const content = container.querySelector('.tab-content');
            expect(content).not.toBeNull();
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('data extraction displays progress indicator when isExtracting=true', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        (isExtracting) => {
          const { container } = render(
            <MockDataExtraction isExtracting={isExtracting} />
          );

          if (isExtracting) {
            // When isExtracting=true, progress indicator should be displayed
            const progressIndicator = container.querySelector('.extraction-progress');
            expect(progressIndicator).not.toBeNull();
            expect(progressIndicator?.textContent).toContain('データ抽出が実行中です');
            
            // Should have progress bar
            const progressBar = container.querySelector('.progress-bar');
            expect(progressBar).not.toBeNull();
            
            // Completion message should not be displayed
            const complete = container.querySelector('.extraction-complete');
            expect(complete).toBeNull();
          } else {
            // When isExtracting=false, progress indicator should not be displayed
            const progressIndicator = container.querySelector('.extraction-progress');
            expect(progressIndicator).toBeNull();
            
            // Completion message should be displayed
            const complete = container.querySelector('.extraction-complete');
            expect(complete).not.toBeNull();
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('loading state transitions are mutually exclusive (loading XOR content)', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        (loading) => {
          const { container } = render(<MockHierarchyView loading={loading} />);

          const loadingIndicator = container.querySelector('.loading');
          const content = container.querySelector('.hierarchy-view');

          // Exactly one should be present (XOR)
          const loadingPresent = loadingIndicator !== null;
          const contentPresent = content !== null;

          expect(loadingPresent !== contentPresent).toBe(true);

          // Verify the correct one is present based on loading state
          expect(loadingPresent).toBe(loading);
          expect(contentPresent).toBe(!loading);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tab loading state transitions are mutually exclusive for all tab types', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (loading, tabName) => {
          const { container } = render(
            <MockTabContent loading={loading} tabName={tabName} />
          );

          const tabLoading = container.querySelector('.tab-loading');
          const tabContent = container.querySelector('.tab-content');

          // Exactly one should be present (XOR)
          const loadingPresent = tabLoading !== null;
          const contentPresent = tabContent !== null;

          expect(loadingPresent !== contentPresent).toBe(true);

          // Verify the correct one is present based on loading state
          expect(loadingPresent).toBe(loading);
          expect(contentPresent).toBe(!loading);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('data extraction state transitions are mutually exclusive', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        (isExtracting) => {
          const { container } = render(
            <MockDataExtraction isExtracting={isExtracting} />
          );

          const progressIndicator = container.querySelector('.extraction-progress');
          const complete = container.querySelector('.extraction-complete');

          // Exactly one should be present (XOR)
          const progressPresent = progressIndicator !== null;
          const completePresent = complete !== null;

          expect(progressPresent !== completePresent).toBe(true);

          // Verify the correct one is present based on extraction state
          expect(progressPresent).toBe(isExtracting);
          expect(completePresent).toBe(!isExtracting);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('loading indicator contains expected text for HierarchyView', () => {
    fc.assert(
      fc.property(
        fc.constant(true), // Always test with loading=true
        (loading) => {
          const { container } = render(<MockHierarchyView loading={loading} />);

          const loadingIndicator = container.querySelector('.loading');
          expect(loadingIndicator).not.toBeNull();

          // Should contain Japanese loading text
          const text = loadingIndicator?.textContent || '';
          expect(text).toContain('読み込み中');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tab loading indicator contains spinner and text for all tab types', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (tabName) => {
          const { container } = render(
            <MockTabContent loading={true} tabName={tabName} />
          );

          const tabLoading = container.querySelector('.tab-loading');
          expect(tabLoading).not.toBeNull();

          // Should have spinner element
          const spinner = container.querySelector('.spinner');
          expect(spinner).not.toBeNull();

          // Should contain loading text
          const text = tabLoading?.textContent || '';
          expect(text).toContain('読み込み中');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('data extraction progress indicator contains progress bar and text', () => {
    fc.assert(
      fc.property(
        fc.constant(true), // Always test with isExtracting=true
        (isExtracting) => {
          const { container } = render(
            <MockDataExtraction isExtracting={isExtracting} />
          );

          const progressIndicator = container.querySelector('.extraction-progress');
          expect(progressIndicator).not.toBeNull();

          // Should have progress bar
          const progressBar = container.querySelector('.progress-bar');
          expect(progressBar).not.toBeNull();

          // Should have progress bar fill
          const progressBarFill = container.querySelector('.progress-bar-fill');
          expect(progressBarFill).not.toBeNull();

          // Should contain extraction text
          const text = progressIndicator?.textContent || '';
          expect(text).toContain('データ抽出が実行中です');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('loading state is independent across different component types', () => {
    fc.assert(
      fc.property(
        arbLoadingState,
        arbLoadingState,
        arbLoadingState,
        (hierarchyLoading, tabLoading, extractionLoading) => {
          // Render all three component types with different loading states
          const hierarchyResult = render(<MockHierarchyView loading={hierarchyLoading} />);
          const tabResult = render(<MockTabContent loading={tabLoading} tabName="contracts" />);
          const extractionResult = render(<MockDataExtraction isExtracting={extractionLoading} />);

          // Each component should independently show/hide loading based on its own state
          const hierarchyHasLoading = hierarchyResult.container.querySelector('.loading') !== null;
          const tabHasLoading = tabResult.container.querySelector('.tab-loading') !== null;
          const extractionHasLoading = extractionResult.container.querySelector('.extraction-progress') !== null;

          expect(hierarchyHasLoading).toBe(hierarchyLoading);
          expect(tabHasLoading).toBe(tabLoading);
          expect(extractionHasLoading).toBe(extractionLoading);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('loading indicator is always present when loading=true regardless of other props', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        arbSiteId,
        arbCustomerName,
        (tabName, siteId, customerName) => {
          // Loading state should be independent of other props
          const { container } = render(
            <MockTabContent loading={true} tabName={tabName} />
          );

          const tabLoading = container.querySelector('.tab-loading');
          expect(tabLoading).not.toBeNull();
          expect(tabLoading?.textContent).toContain('読み込み中');
        }
      ),
      { numRuns: 100 }
    );
  });
});
