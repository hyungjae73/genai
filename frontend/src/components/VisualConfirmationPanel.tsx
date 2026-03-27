import React, { useState, useCallback, useMemo } from 'react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import type { ManualExtractionInput } from '../types/extractedData';
import { saveManualExtraction } from '../api/extractedData';
import './VisualConfirmationPanel.css';

interface VisualConfirmationPanelProps {
  crawlResultId: number;
  screenshotUrl: string | null;
  rawHtml: string | null;
  extractionStatus: 'no_data' | 'partial' | 'complete';
  onSaved?: () => void;
}

/** Escape HTML special characters so raw HTML is displayed as text. */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Escape special regex characters in a user-provided search string. */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

interface ValidationErrors {
  product_name?: string;
  price?: string;
}

const VisualConfirmationPanel: React.FC<VisualConfirmationPanelProps> = ({
  crawlResultId,
  screenshotUrl,
  rawHtml,
  extractionStatus,
  onSaved,
}) => {
  const [activeTab, setActiveTab] = useState<'screenshot' | 'html'>('screenshot');
  const [htmlSearch, setHtmlSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errors, setErrors] = useState<ValidationErrors>({});

  const [form, setForm] = useState<ManualExtractionInput>({
    product_name: '',
    price: '',
    currency: 'JPY',
    payment_methods: [],
    additional_fees: '',
  });

  const handleFieldChange = useCallback(
    (field: keyof ManualExtractionInput, value: string | string[]) => {
      setForm((prev) => ({ ...prev, [field]: value }));
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    },
    [],
  );

  const handlePaymentMethodsChange = useCallback((value: string) => {
    const methods = value
      .split(',')
      .map((m) => m.trim())
      .filter(Boolean);
    setForm((prev) => ({ ...prev, payment_methods: methods }));
  }, []);

  const validate = useCallback((): boolean => {
    const next: ValidationErrors = {};
    if (!form.product_name?.trim()) {
      next.product_name = '商品名は必須です';
    }
    if (form.price && form.price.trim() !== '') {
      const num = Number(form.price);
      if (isNaN(num) || num < 0) {
        next.price = '価格は0以上の数値を入力してください';
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }, [form]);

  const handleSave = useCallback(async () => {
    if (!validate()) return;
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      await saveManualExtraction(crawlResultId, form);
      setSaveSuccess(true);
      onSaved?.();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : '保存に失敗しました');
    } finally {
      setSaving(false);
    }
  }, [crawlResultId, form, onSaved, validate]);

  /** Build safe highlighted HTML string for the raw HTML viewer. */
  const highlightedHtml = useMemo(() => {
    if (!rawHtml) return '';
    const escaped = escapeHtml(rawHtml);
    if (!htmlSearch.trim()) return escaped;
    try {
      const pattern = new RegExp(`(${escapeRegex(htmlSearch)})`, 'gi');
      return escaped.replace(pattern, '<mark>$1</mark>');
    } catch {
      return escaped;
    }
  }, [rawHtml, htmlSearch]);

  const statusLabel =
    extractionStatus === 'no_data'
      ? '抽出データなし'
      : extractionStatus === 'partial'
        ? '部分抽出'
        : '抽出完了';

  return (
    <div className="visual-confirmation">
      <div className="visual-confirmation__header">
        <span className="visual-confirmation__warning-icon" role="img" aria-label="warning">⚠</span>
        <span>目視確認モード: {statusLabel}</span>
      </div>

      <div className="visual-confirmation__viewer">
        <div className="visual-confirmation__tabs" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'screenshot'}
            className={`visual-confirmation__tab ${activeTab === 'screenshot' ? 'visual-confirmation__tab--active' : ''}`}
            onClick={() => setActiveTab('screenshot')}
          >
            スクリーンショット
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'html'}
            className={`visual-confirmation__tab ${activeTab === 'html' ? 'visual-confirmation__tab--active' : ''}`}
            onClick={() => setActiveTab('html')}
          >
            生HTML
          </button>
        </div>

        {activeTab === 'screenshot' && (
          <div className="visual-confirmation__screenshot-panel">
            {screenshotUrl ? (
              <TransformWrapper
                initialScale={1}
                minScale={0.25}
                maxScale={4}
                centerOnInit
              >
                {({ zoomIn, zoomOut, resetTransform }) => (
                  <>
                    <div className="visual-confirmation__zoom-controls">
                      <button onClick={() => zoomIn()} aria-label="ズームイン">+</button>
                      <button onClick={() => zoomOut()} aria-label="ズームアウト">−</button>
                      <button onClick={() => resetTransform()} aria-label="リセット">リセット</button>
                    </div>
                    <TransformComponent
                      wrapperStyle={{ width: '100%', maxHeight: '400px', overflow: 'hidden' }}
                      contentStyle={{ width: '100%' }}
                    >
                      <img
                        src={screenshotUrl}
                        alt="ページスクリーンショット"
                        loading="lazy"
                        style={{ width: '100%', display: 'block' }}
                      />
                    </TransformComponent>
                  </>
                )}
              </TransformWrapper>
            ) : (
              <div className="visual-confirmation__empty">スクリーンショットがありません</div>
            )}
          </div>
        )}

        {activeTab === 'html' && (
          <div className="visual-confirmation__html-panel">
            <div className="visual-confirmation__html-search">
              <label htmlFor="html-search">検索:</label>
              <input
                id="html-search"
                type="text"
                value={htmlSearch}
                onChange={(e) => setHtmlSearch(e.target.value)}
                placeholder="HTMLを検索..."
              />
            </div>
            {rawHtml ? (
              <pre
                className="visual-confirmation__html-content"
                dangerouslySetInnerHTML={{ __html: highlightedHtml }}
              />
            ) : (
              <div className="visual-confirmation__empty">HTMLデータがありません</div>
            )}
          </div>
        )}
      </div>

      <div className="visual-confirmation__form">
        <h3>手動入力フォーム</h3>
        <div className="visual-confirmation__form-grid">
          <div className="visual-confirmation__field">
            <label htmlFor="vc-product-name">商品名 *</label>
            <input
              id="vc-product-name"
              type="text"
              value={form.product_name || ''}
              onChange={(e) => handleFieldChange('product_name', e.target.value)}
              disabled={saving || saveSuccess}
              aria-invalid={!!errors.product_name}
              aria-describedby={errors.product_name ? 'vc-product-name-error' : undefined}
            />
            {errors.product_name && (
              <span id="vc-product-name-error" className="visual-confirmation__field-error">
                {errors.product_name}
              </span>
            )}
          </div>
          <div className="visual-confirmation__field">
            <label htmlFor="vc-price">価格</label>
            <input
              id="vc-price"
              type="text"
              inputMode="decimal"
              value={form.price || ''}
              onChange={(e) => handleFieldChange('price', e.target.value)}
              disabled={saving || saveSuccess}
              aria-invalid={!!errors.price}
              aria-describedby={errors.price ? 'vc-price-error' : undefined}
            />
            {errors.price && (
              <span id="vc-price-error" className="visual-confirmation__field-error">
                {errors.price}
              </span>
            )}
          </div>
          <div className="visual-confirmation__field">
            <label htmlFor="vc-currency">通貨</label>
            <input
              id="vc-currency"
              type="text"
              value={form.currency || ''}
              onChange={(e) => handleFieldChange('currency', e.target.value)}
              disabled={saving || saveSuccess}
            />
          </div>
          <div className="visual-confirmation__field">
            <label htmlFor="vc-payment-methods">支払方法 (カンマ区切り)</label>
            <input
              id="vc-payment-methods"
              type="text"
              value={form.payment_methods?.join(', ') || ''}
              onChange={(e) => handlePaymentMethodsChange(e.target.value)}
              disabled={saving || saveSuccess}
            />
          </div>
          <div className="visual-confirmation__field visual-confirmation__field--full">
            <label htmlFor="vc-fees">追加手数料</label>
            <input
              id="vc-fees"
              type="text"
              value={form.additional_fees || ''}
              onChange={(e) => handleFieldChange('additional_fees', e.target.value)}
              disabled={saving || saveSuccess}
            />
          </div>
        </div>

        {saveError && <div className="visual-confirmation__error" role="alert">{saveError}</div>}
        {saveSuccess && <div className="visual-confirmation__success" role="status">保存しました</div>}

        <button
          className="visual-confirmation__save-btn"
          onClick={handleSave}
          disabled={saving || saveSuccess}
        >
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
};

export default VisualConfirmationPanel;
