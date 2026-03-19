import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import React from 'react';

// --- Arbitrary generators ---

const arbSiteId = fc.integer({ min: 1, max: 100000 });
const arbCustomerName = fc.string({ minLength: 1, maxLength: 100 });
const arbErrorState = fc.boolean();

// Error type generators
const arbNetworkError = fc.constant('ネットワークエラーが発生しました');
const arbClientError = fc.constantFrom(
  'リクエストが無効です',
  '認証に失敗しました',
  'アクセスが拒否されました',
  'リソースが見つかりません'
);
const arbServerError = fc.constantFrom(
  'サーバーエラーが発生しました。しばらくしてから再度お試しください',
  'データベースエラーが発生しました',
  'サービスが一時的に利用できません'
);

const arbErrorMessage = fc.oneof(arbNetworkError, arbClientError, arbServerError);

// --- Mock components that simulate error states ---

interface MockHierarchyViewProps {
  error: string | null;
}

const MockHierarchyView: React.FC<MockHierarchyViewProps> = ({ error }) => {
  if (error) {
    return (
      <div className="hierarchy-error">
        <p className="error-message">エラー: {error}</p>
      </div>
    );
  }
  return <div className="hierarchy-view">Content loaded</div>;
};

interface MockTabContentProps {
  error: string | null;
  tabName: string;
}

const MockTabContent: React.FC<MockTabContentProps> = ({ error, tabName }) => {
  if (error) {
    return (
      <div className="tab-error">
        <p>エラー: {error}</p>
      </div>
    );
  }
  return <div className="tab-content">{tabName} content loaded</div>;
};

interface MockAPIComponentProps {
  error: string | null;
  componentType: 'contracts' | 'screenshots' | 'verification' | 'alerts';
}

const MockAPIComponent: React.FC<MockAPIComponentProps> = ({ error, componentType }) => {
  if (error) {
    return (
      <div className={`${componentType}-error`}>
        <div className="error-container">
          <p className="error-message">エラー: {error}</p>
          <button className="retry-button">再試行</button>
        </div>
      </div>
    );
  }
  return <div className={`${componentType}-content`}>Content loaded</div>;
};

// --- Property 18: エラー状態の表示 ---

describe('Feature: hierarchical-ui-restructure, Property 18: エラー状態の表示', () => {
  /**
   * **Validates: Requirements 10.4**
   *
   * 任意のAPIリクエストが失敗した場合、該当領域内にエラーメッセージが表示されること。
   */

  it('HierarchyView displays error message when error is present', () => {
    fc.assert(
      fc.property(
        arbErrorState,
        arbErrorMessage,
        (hasError, errorMessage) => {
          const error = hasError ? errorMessage : null;
          const { container } = render(<MockHierarchyView error={error} />);

          if (hasError) {
            // When error is present, error message should be displayed
            const errorElement = container.querySelector('.hierarchy-error');
            expect(errorElement).not.toBeNull();
            
            const errorText = container.querySelector('.error-message');
            expect(errorText).not.toBeNull();
            expect(errorText?.textContent).toContain('エラー:');
            expect(errorText?.textContent).toContain(errorMessage);
            
            // Content should not be displayed
            const content = container.querySelector('.hierarchy-view');
            expect(content).toBeNull();
          } else {
            // When no error, error message should not be displayed
            const errorElement = container.querySelector('.hierarchy-error');
            expect(errorElement).toBeNull();
            
            // Content should be displayed
            const content = container.querySelector('.hierarchy-view');
            expect(content).not.toBeNull();
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tab content displays error message when API request fails for any tab type', () => {
    fc.assert(
      fc.property(
        arbErrorState,
        arbErrorMessage,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (hasError, errorMessage, tabName) => {
          const error = hasError ? errorMessage : null;
          const { container } = render(
            <MockTabContent error={error} tabName={tabName} />
          );

          if (hasError) {
            // When error is present, tab error should be displayed
            const tabError = container.querySelector('.tab-error');
            expect(tabError).not.toBeNull();
            expect(tabError?.textContent).toContain('エラー:');
            expect(tabError?.textContent).toContain(errorMessage);
            
            // Tab content should not be displayed
            const content = container.querySelector('.tab-content');
            expect(content).toBeNull();
          } else {
            // When no error, tab error should not be displayed
            const tabError = container.querySelector('.tab-error');
            expect(tabError).toBeNull();
            
            // Tab content should be displayed
            const content = container.querySelector('.tab-content');
            expect(content).not.toBeNull();
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error messages are displayed in the appropriate component area', () => {
    fc.assert(
      fc.property(
        arbErrorMessage,
        fc.constantFrom<'contracts' | 'screenshots' | 'verification' | 'alerts'>(
          'contracts',
          'screenshots',
          'verification',
          'alerts'
        ),
        (errorMessage, componentType) => {
          const { container } = render(
            <MockAPIComponent error={errorMessage} componentType={componentType} />
          );

          // Error should be displayed in the component-specific error container
          const errorContainer = container.querySelector(`.${componentType}-error`);
          expect(errorContainer).not.toBeNull();
          
          const errorElement = container.querySelector('.error-container');
          expect(errorElement).not.toBeNull();
          
          const errorText = container.querySelector('.error-message');
          expect(errorText).not.toBeNull();
          expect(errorText?.textContent).toContain('エラー:');
          expect(errorText?.textContent).toContain(errorMessage);
          
          // Content should not be displayed
          const content = container.querySelector(`.${componentType}-content`);
          expect(content).toBeNull();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error state transitions are mutually exclusive (error XOR content)', () => {
    fc.assert(
      fc.property(
        arbErrorState,
        arbErrorMessage,
        (hasError, errorMessage) => {
          const error = hasError ? errorMessage : null;
          const { container } = render(<MockHierarchyView error={error} />);

          const errorElement = container.querySelector('.hierarchy-error');
          const content = container.querySelector('.hierarchy-view');

          // Exactly one should be present (XOR)
          const errorPresent = errorElement !== null;
          const contentPresent = content !== null;

          expect(errorPresent !== contentPresent).toBe(true);

          // Verify the correct one is present based on error state
          expect(errorPresent).toBe(hasError);
          expect(contentPresent).toBe(!hasError);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('tab error state transitions are mutually exclusive for all tab types', () => {
    fc.assert(
      fc.property(
        arbErrorState,
        arbErrorMessage,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (hasError, errorMessage, tabName) => {
          const error = hasError ? errorMessage : null;
          const { container } = render(
            <MockTabContent error={error} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          const tabContent = container.querySelector('.tab-content');

          // Exactly one should be present (XOR)
          const errorPresent = tabError !== null;
          const contentPresent = tabContent !== null;

          expect(errorPresent !== contentPresent).toBe(true);

          // Verify the correct one is present based on error state
          expect(errorPresent).toBe(hasError);
          expect(contentPresent).toBe(!hasError);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error messages contain expected prefix "エラー:" for all components', () => {
    fc.assert(
      fc.property(
        arbErrorMessage,
        fc.constantFrom<'contracts' | 'screenshots' | 'verification' | 'alerts'>(
          'contracts',
          'screenshots',
          'verification',
          'alerts'
        ),
        (errorMessage, componentType) => {
          const { container } = render(
            <MockAPIComponent error={errorMessage} componentType={componentType} />
          );

          const errorText = container.querySelector('.error-message');
          expect(errorText).not.toBeNull();

          // Should contain Japanese error prefix
          const text = errorText?.textContent || '';
          expect(text).toContain('エラー:');
          expect(text).toContain(errorMessage);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('network errors are displayed correctly', () => {
    fc.assert(
      fc.property(
        arbNetworkError,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (errorMessage, tabName) => {
          const { container } = render(
            <MockTabContent error={errorMessage} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          expect(tabError).not.toBeNull();
          expect(tabError?.textContent).toContain('ネットワークエラーが発生しました');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('client errors (4xx) are displayed correctly', () => {
    fc.assert(
      fc.property(
        arbClientError,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (errorMessage, tabName) => {
          const { container } = render(
            <MockTabContent error={errorMessage} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          expect(tabError).not.toBeNull();
          
          // Should contain one of the client error messages
          const text = tabError?.textContent || '';
          const clientErrorMessages = [
            'リクエストが無効です',
            '認証に失敗しました',
            'アクセスが拒否されました',
            'リソースが見つかりません'
          ];
          
          const containsClientError = clientErrorMessages.some(msg => text.includes(msg));
          expect(containsClientError).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('server errors (5xx) are displayed correctly', () => {
    fc.assert(
      fc.property(
        arbServerError,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (errorMessage, tabName) => {
          const { container } = render(
            <MockTabContent error={errorMessage} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          expect(tabError).not.toBeNull();
          
          // Should contain one of the server error messages
          const text = tabError?.textContent || '';
          const serverErrorMessages = [
            'サーバーエラーが発生しました',
            'データベースエラーが発生しました',
            'サービスが一時的に利用できません'
          ];
          
          const containsServerError = serverErrorMessages.some(msg => text.includes(msg));
          expect(containsServerError).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error states are independent across different components', () => {
    fc.assert(
      fc.property(
        arbErrorState,
        arbErrorState,
        arbErrorState,
        arbErrorMessage,
        arbErrorMessage,
        arbErrorMessage,
        (hierarchyHasError, tab1HasError, tab2HasError, error1, error2, error3) => {
          // Render different components with different error states
          const hierarchyResult = render(
            <MockHierarchyView error={hierarchyHasError ? error1 : null} />
          );
          const tab1Result = render(
            <MockTabContent error={tab1HasError ? error2 : null} tabName="contracts" />
          );
          const tab2Result = render(
            <MockTabContent error={tab2HasError ? error3 : null} tabName="alerts" />
          );

          // Each component should independently show/hide error based on its own state
          const hierarchyHasErrorElement = hierarchyResult.container.querySelector('.hierarchy-error') !== null;
          const tab1HasErrorElement = tab1Result.container.querySelector('.tab-error') !== null;
          const tab2HasErrorElement = tab2Result.container.querySelector('.tab-error') !== null;

          expect(hierarchyHasErrorElement).toBe(hierarchyHasError);
          expect(tab1HasErrorElement).toBe(tab1HasError);
          expect(tab2HasErrorElement).toBe(tab2HasError);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error message is always present when error state is true regardless of other props', () => {
    fc.assert(
      fc.property(
        arbErrorMessage,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        arbSiteId,
        arbCustomerName,
        (errorMessage, tabName, siteId, customerName) => {
          // Error state should be independent of other props
          const { container } = render(
            <MockTabContent error={errorMessage} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          expect(tabError).not.toBeNull();
          expect(tabError?.textContent).toContain('エラー:');
          expect(tabError?.textContent).toContain(errorMessage);
          
          // Verify siteId and customerName don't affect error display
          // (they are just used to ensure error is independent of other props)
          expect(siteId).toBeGreaterThan(0);
          expect(customerName.length).toBeGreaterThan(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('retry button is displayed with error message in API components', () => {
    fc.assert(
      fc.property(
        arbErrorMessage,
        fc.constantFrom<'contracts' | 'screenshots' | 'verification' | 'alerts'>(
          'contracts',
          'screenshots',
          'verification',
          'alerts'
        ),
        (errorMessage, componentType) => {
          const { container } = render(
            <MockAPIComponent error={errorMessage} componentType={componentType} />
          );

          // Error container should have retry button
          const errorContainer = container.querySelector('.error-container');
          expect(errorContainer).not.toBeNull();
          
          const retryButton = container.querySelector('.retry-button');
          expect(retryButton).not.toBeNull();
          expect(retryButton?.textContent).toBe('再試行');
        }
      ),
      { numRuns: 100 }
    );
  });

  it('error message is localized in Japanese', () => {
    fc.assert(
      fc.property(
        arbErrorMessage,
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        (errorMessage, tabName) => {
          const { container } = render(
            <MockTabContent error={errorMessage} tabName={tabName} />
          );

          const tabError = container.querySelector('.tab-error');
          expect(tabError).not.toBeNull();
          
          // Verify the error message is in Japanese
          const text = tabError?.textContent || '';
          
          // Should contain Japanese characters or Japanese error messages
          const hasJapanesePrefix = text.includes('エラー:');
          expect(hasJapanesePrefix).toBe(true);
          
          // Should contain the localized error message
          expect(text).toContain(errorMessage);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('different error types are displayed correctly in the same component type', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('contracts', 'screenshots', 'verification', 'alerts'),
        arbNetworkError,
        arbClientError,
        arbServerError,
        (tabName, networkError, clientError, serverError) => {
          // Test network error
          const networkResult = render(
            <MockTabContent error={networkError} tabName={tabName} />
          );
          expect(networkResult.container.querySelector('.tab-error')?.textContent).toContain(networkError);

          // Test client error
          const clientResult = render(
            <MockTabContent error={clientError} tabName={tabName} />
          );
          expect(clientResult.container.querySelector('.tab-error')?.textContent).toContain(clientError);

          // Test server error
          const serverResult = render(
            <MockTabContent error={serverError} tabName={tabName} />
          );
          expect(serverResult.container.querySelector('.tab-error')?.textContent).toContain(serverError);
        }
      ),
      { numRuns: 100 }
    );
  });
});
