import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { fetchExtractedData, updateExtractedData, fetchVisualConfirmationData } from '../api/extractedData';
import type {
  ExtractedPaymentInfo,
  ExtractedPaymentInfoUpdate,
  PriceInfo,
  PaymentMethod,
  Fee,
  VisualConfirmationData,
} from '../types/extractedData';
import ConfidenceIndicator, { sortByConfidenceAsc } from '../components/ConfidenceIndicator';
import EditableField from '../components/EditableField';
import type { FieldType } from '../components/EditableField';
import ChangeHistoryPanel from '../components/ChangeHistoryPanel';
import ApprovalWorkflow from '../components/ApprovalWorkflow';
import VisualConfirmationPanel from '../components/VisualConfirmationPanel';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './CrawlResultReview.css';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

/* ------------------------------------------------------------------ */
/*  ScreenshotViewer – zoom & pan via react-zoom-pan-pinch             */
/* ------------------------------------------------------------------ */

interface ScreenshotViewerProps {
  screenshotUrl: string;
  highlightedField: string | null;
}

const ScreenshotViewer: React.FC<ScreenshotViewerProps> = ({
  screenshotUrl,
  highlightedField,
}) => {
  return (
    <div className="screenshot-viewer-container">
      <TransformWrapper
        initialScale={1}
        minScale={0.5}
        maxScale={4}
        centerOnInit
      >
        {({ zoomIn, zoomOut, resetTransform }) => (
          <>
            <div className="screenshot-controls">
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => zoomIn()}
                aria-label="ズームイン"
              >
                🔍+
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => zoomOut()}
                aria-label="ズームアウト"
              >
                🔍−
              </button>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => resetTransform()}
                aria-label="リセット"
              >
                ↺ リセット
              </button>
            </div>
            <TransformComponent
              wrapperStyle={{ width: '100%', height: '100%' }}
              contentStyle={{ width: '100%' }}
            >
              <img
                src={screenshotUrl}
                alt="クロール結果スクリーンショット"
                loading="lazy"
                style={{ width: '100%', display: 'block' }}
              />
            </TransformComponent>
            {highlightedField && (
              <div className="screenshot-highlight-indicator">
                選択中: {highlightedField}
              </div>
            )}
          </>
        )}
      </TransformWrapper>
    </div>
  );
};


/* ------------------------------------------------------------------ */
/*  DataFieldRow – clickable row with ConfidenceIndicator & editing    */
/* ------------------------------------------------------------------ */

interface DataFieldRowProps {
  label: string;
  value: string;
  fieldKey: string;
  confidence?: number;
  isHighlighted: boolean;
  isManuallyEdited?: boolean;
  fieldType?: FieldType;
  onClick: (fieldKey: string) => void;
  onSave?: (newValue: string) => Promise<void>;
}

const DataFieldRow: React.FC<DataFieldRowProps> = ({
  label,
  value,
  fieldKey,
  confidence,
  isHighlighted,
  isManuallyEdited = false,
  fieldType = 'text',
  onClick,
  onSave,
}) => (
  <tr
    className={`data-field-row ${isHighlighted ? 'data-field-row--highlighted' : ''}`}
    onClick={() => onClick(fieldKey)}
    style={{ cursor: 'pointer' }}
    role="button"
    tabIndex={0}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') onClick(fieldKey);
    }}
    aria-label={`${label}: ${value}`}
  >
    <td className="data-field-label">{label}</td>
    <td className="data-field-value" onClick={(e) => e.stopPropagation()}>
      {onSave ? (
        <EditableField
          value={value}
          fieldType={fieldType}
          isManuallyEdited={isManuallyEdited}
          onSave={onSave}
        />
      ) : (
        value
      )}
    </td>
    <td className="data-field-confidence">
      {confidence !== undefined && (
        <ConfidenceIndicator score={confidence} compact />
      )}
    </td>
  </tr>
);

/* ------------------------------------------------------------------ */
/*  AddFieldForm – add a new manually-entered field                    */
/* ------------------------------------------------------------------ */

interface AddFieldFormProps {
  onAdd: (label: string, value: string) => Promise<void>;
}

const AddFieldForm: React.FC<AddFieldFormProps> = ({ onAdd }) => {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState('');
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!label.trim() || !value.trim()) return;
    setSaving(true);
    try {
      await onAdd(label.trim(), value.trim());
      setLabel('');
      setValue('');
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        className="add-field-btn"
        onClick={() => setOpen(true)}
        style={{
          marginTop: '0.5rem',
          padding: '0.3rem 0.6rem',
          fontSize: '0.8rem',
          backgroundColor: 'transparent',
          border: '1px dashed var(--border-color, #e5e7eb)',
          borderRadius: '4px',
          cursor: 'pointer',
          color: 'var(--text-secondary, #6b7280)',
        }}
      >
        ＋ フィールド追加
      </button>
    );
  }

  return (
    <div className="add-field-form" style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
      <input
        type="text"
        placeholder="項目名"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        style={{ padding: '0.2rem 0.4rem', fontSize: '0.8rem', border: '1px solid var(--border-color, #e5e7eb)', borderRadius: '4px', width: '100px' }}
        aria-label="新規フィールド名"
      />
      <input
        type="text"
        placeholder="値"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        style={{ padding: '0.2rem 0.4rem', fontSize: '0.8rem', border: '1px solid var(--border-color, #e5e7eb)', borderRadius: '4px', width: '150px' }}
        aria-label="新規フィールド値"
      />
      <button
        type="button"
        onClick={handleSubmit}
        disabled={saving || !label.trim() || !value.trim()}
        style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', backgroundColor: 'var(--success-color, #10b981)', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
      >
        {saving ? '...' : '追加'}
      </button>
      <button
        type="button"
        onClick={() => { setOpen(false); setLabel(''); setValue(''); }}
        style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem', backgroundColor: 'var(--text-secondary, #6b7280)', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
      >
        キャンセル
      </button>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  Helper: build sortable field descriptors for a section             */
/* ------------------------------------------------------------------ */

interface FieldDescriptor {
  label: string;
  value: string;
  fieldKey: string;
  confidence: number | undefined;
  fieldType: FieldType;
  /** key path used to build the update payload */
  section: 'product_info' | 'price_info' | 'payment_methods' | 'fees';
  index?: number;
  subField?: string;
}

/* ------------------------------------------------------------------ */
/*  Main page component                                                */
/* ------------------------------------------------------------------ */

const CrawlResultReviewPage: React.FC = () => {
  const { crawlResultId } = useParams<{ siteId: string; crawlResultId: string }>();

  const [data, setData] = useState<ExtractedPaymentInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [highlightedField, setHighlightedField] = useState<string | null>(null);
  const [manuallyEditedFields, setManuallyEditedFields] = useState<Set<string>>(new Set());
  const [visualConfirmation, setVisualConfirmation] = useState<VisualConfirmationData | null>(null);

  useEffect(() => {
    if (!crawlResultId) return;
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch extracted data and visual confirmation data in parallel
        const [extractedResult, vcResult] = await Promise.allSettled([
          fetchExtractedData(Number(crawlResultId)),
          fetchVisualConfirmationData(Number(crawlResultId)),
        ]);

        if (!cancelled) {
          if (extractedResult.status === 'fulfilled') {
            setData(extractedResult.value);
          }
          if (vcResult.status === 'fulfilled') {
            setVisualConfirmation(vcResult.value);
          }
          // If both fail, show error
          if (extractedResult.status === 'rejected' && vcResult.status === 'rejected') {
            const message =
              extractedResult.reason instanceof Error
                ? extractedResult.reason.message
                : 'データの取得に失敗しました';
            setError(message);
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : 'データの取得に失敗しました';
          setError(message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [crawlResultId]);

  const handleFieldClick = useCallback((fieldKey: string) => {
    setHighlightedField((prev) => (prev === fieldKey ? null : fieldKey));
  }, []);

  /* ---- Save handler: updates API and local state ---- */

  const handleSaveField = useCallback(
    async (fieldKey: string, newValue: string, section: string, subField?: string, index?: number) => {
      if (!data) return;

      const update: ExtractedPaymentInfoUpdate = {};

      if (section === 'product_info') {
        const key = subField ?? fieldKey;
        update.product_info = { ...data.product_info, [key]: newValue };
      } else if (section === 'price_info' && index !== undefined && data.price_info) {
        const updated = [...data.price_info];
        updated[index] = { ...updated[index], amount: Number(newValue.replace(/,/g, '')) || 0 };
        update.price_info = updated;
      } else if (section === 'payment_methods' && index !== undefined && data.payment_methods) {
        const updated = [...data.payment_methods];
        updated[index] = { ...updated[index], method_name: newValue };
        update.payment_methods = updated;
      } else if (section === 'fees' && index !== undefined && data.fees) {
        const updated = [...data.fees];
        updated[index] = { ...updated[index], amount: Number(newValue.replace(/,/g, '')) || 0 };
        update.fees = updated;
      }

      const result = await updateExtractedData(data.id, update);
      setData(result);
      setManuallyEditedFields((prev) => new Set(prev).add(fieldKey));
    },
    [data],
  );

  /* ---- Add new product_info field ---- */

  const handleAddProductField = useCallback(
    async (label: string, value: string) => {
      if (!data) return;
      const key = label.toLowerCase().replace(/\s+/g, '_');
      const update: ExtractedPaymentInfoUpdate = {
        product_info: { ...data.product_info, [key]: value },
      };
      const result = await updateExtractedData(data.id, update);
      setData(result);
      setManuallyEditedFields((prev) => new Set(prev).add(`product_${key}`));
    },
    [data],
  );

  /* ---- Approval status change handler ---- */

  const handleStatusChange = useCallback(
    (newStatus: 'approved' | 'rejected') => {
      setData((prev) => prev ? { ...prev, status: newStatus } : prev);
    },
    [],
  );

  /** Refresh visual confirmation data after manual save */
  const handleVisualConfirmationSaved = useCallback(() => {
    if (!crawlResultId) return;
    fetchVisualConfirmationData(Number(crawlResultId)).then((vc) => {
      setVisualConfirmation(vc);
    }).catch(() => { /* ignore refresh errors */ });
    fetchExtractedData(Number(crawlResultId)).then((d) => {
      setData(d);
    }).catch(() => { /* ignore refresh errors */ });
  }, [crawlResultId]);

  /* ---- Loading / Error states ---- */

  if (loading) {
    return (
      <div className="crawl-review" role="status">
        <p>読み込み中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="crawl-review">
        <div className="error-message" role="alert">
          <p>エラー: {error}</p>
          <Link to="/" className="btn btn-secondary">
            ダッシュボードに戻る
          </Link>
        </div>
      </div>
    );
  }

  if (!data) {
    // No extracted data — show visual confirmation panel if available
    if (visualConfirmation && visualConfirmation.extraction_status !== 'complete') {
      return (
        <div className="crawl-review">
          <div className="crawl-review__header">
            <div className="crawl-review__header-left">
              <h1>クロール結果レビュー <HelpButton title="クロール結果レビューの使い方">
                <div className="help-content">
                  <h3>ユーザーストーリー</h3>
                  <p>クロールで取得したデータを確認・編集し、抽出精度を検証したい</p>

                  <h3>スクリーンショットとデータの並列表示</h3>
                  <p>画面左側にスクリーンショット、右側に抽出データが並列表示されます。ズーム・パン操作でスクリーンショットの詳細を確認できます。</p>

                  <h3>フィールドハイライト</h3>
                  <p>右側のデータフィールドをクリックすると、スクリーンショット上の該当箇所がハイライト表示されます。もう一度クリックするとハイライトが解除されます。</p>

                  <h3>承認ワークフロー</h3>
                  <p>抽出データの確認後、承認または却下の操作が可能です。データの手動編集も行えます。</p>

                  <h3>HTML解析とOCR解析の比較</h3>
                  <p>HTML解析とOCR解析の結果を比較し、抽出精度を検証できます。信頼度スコアが低いフィールドは優先的に確認してください。</p>
                </div>
              </HelpButton></h1>
            </div>
          </div>
          <div className="crawl-review__body">
            <div className="crawl-review__visual-confirmation-full">
              <VisualConfirmationPanel
                crawlResultId={Number(crawlResultId)}
                screenshotUrl={visualConfirmation.screenshot_url}
                rawHtml={visualConfirmation.raw_html}
                extractionStatus={visualConfirmation.extraction_status}
                onSaved={handleVisualConfirmationSaved}
              />
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="crawl-review">
        <p>データが見つかりません。</p>
      </div>
    );
  }

  /* ---- Derived values ---- */

  const screenshotUrl = data.metadata?.screenshot_path
    ? `${API_BASE_URL}/${(data.metadata.screenshot_path as string).replace(/^\//, '')}`
    : null;

  const siteUrl = (data.metadata?.url as string) ?? '—';
  const crawlTimestamp = data.extracted_at
    ? new Date(data.extracted_at).toLocaleString('ja-JP')
    : '—';

  const overallConfidence = data.overall_confidence_score ?? 0;

  /* ---- Build sortable product fields (sorted by confidence ascending) ---- */

  const productFields: FieldDescriptor[] = [];
  if (data.product_info) {
    const pi = data.product_info;
    const cs = data.confidence_scores;
    if (pi.name) productFields.push({ label: '商品名', value: pi.name, fieldKey: 'product_name', confidence: cs?.product_name, fieldType: 'text', section: 'product_info', subField: 'name' });
    if (pi.description) productFields.push({ label: '説明', value: pi.description, fieldKey: 'product_description', confidence: cs?.product_description, fieldType: 'text', section: 'product_info', subField: 'description' });
    if (pi.sku) productFields.push({ label: 'SKU', value: pi.sku, fieldKey: 'product_sku', confidence: cs?.sku, fieldType: 'text', section: 'product_info', subField: 'sku' });
    if (pi.category) productFields.push({ label: 'カテゴリ', value: pi.category, fieldKey: 'product_category', confidence: cs?.category, fieldType: 'text', section: 'product_info', subField: 'category' });
    if (pi.brand) productFields.push({ label: 'ブランド', value: pi.brand, fieldKey: 'product_brand', confidence: cs?.brand, fieldType: 'text', section: 'product_info', subField: 'brand' });
  }
  const sortedProductFields = sortByConfidenceAsc(productFields, (f) => f.confidence);

  /* ---- Render ---- */

  return (
    <div className="crawl-review">
      {/* Header bar */}
      <div className="crawl-review__header">
        <div className="crawl-review__header-left">
          <h1>クロール結果レビュー <HelpButton title="クロール結果レビューの使い方">
            <div className="help-content">
              <h3>ユーザーストーリー</h3>
              <p>クロールで取得したデータを確認・編集し、抽出精度を検証したい</p>

              <h3>スクリーンショットとデータの並列表示</h3>
              <p>画面左側にスクリーンショット、右側に抽出データが並列表示されます。ズーム・パン操作でスクリーンショットの詳細を確認できます。</p>

              <h3>フィールドハイライト</h3>
              <p>右側のデータフィールドをクリックすると、スクリーンショット上の該当箇所がハイライト表示されます。もう一度クリックするとハイライトが解除されます。</p>

              <h3>承認ワークフロー</h3>
              <p>抽出データの確認後、承認または却下の操作が可能です。データの手動編集も行えます。</p>

              <h3>HTML解析とOCR解析の比較</h3>
              <p>HTML解析とOCR解析の結果を比較し、抽出精度を検証できます。信頼度スコアが低いフィールドは優先的に確認してください。</p>
            </div>
          </HelpButton></h1>
          <span className="crawl-review__meta">
            クロール日時: {crawlTimestamp}
          </span>
          <span className="crawl-review__meta">
            サイトURL:{' '}
            <a href={siteUrl} target="_blank" rel="noopener noreferrer">
              {siteUrl}
            </a>
          </span>
        </div>
        <div className="crawl-review__header-right">
          <ConfidenceIndicator score={overallConfidence} fieldName="全体信頼度" />
          <span className={`status-badge status-badge--${data.status}`}>
            {data.status === 'pending' && '保留中'}
            {data.status === 'approved' && '承認済み'}
            {data.status === 'rejected' && '却下'}
            {data.status === 'failed' && '失敗'}
          </span>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="crawl-review__body">
        {/* Left: Screenshot */}
        <div className="crawl-review__screenshot">
          {screenshotUrl ? (
            <ScreenshotViewer
              screenshotUrl={screenshotUrl}
              highlightedField={highlightedField}
            />
          ) : (
            <div className="no-screenshot">
              <p>スクリーンショットがありません</p>
            </div>
          )}
        </div>

        {/* Right: Extracted data */}
        <div className="crawl-review__data">
          <h2>抽出データ</h2>

          {/* Product info – sorted by confidence ascending */}
          {sortedProductFields.length > 0 && (
            <section className="data-section">
              <h3>商品情報</h3>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>項目</th>
                    <th>値</th>
                    <th>信頼度</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedProductFields.map((f) => (
                    <DataFieldRow
                      key={f.fieldKey}
                      label={f.label}
                      value={f.value}
                      fieldKey={f.fieldKey}
                      confidence={f.confidence}
                      isHighlighted={highlightedField === f.fieldKey}
                      isManuallyEdited={manuallyEditedFields.has(f.fieldKey)}
                      fieldType={f.fieldType}
                      onClick={handleFieldClick}
                      onSave={async (newVal) => handleSaveField(f.fieldKey, newVal, f.section, f.subField)}
                    />
                  ))}
                </tbody>
              </table>
              <AddFieldForm onAdd={handleAddProductField} />
            </section>
          )}

          {/* Price info – sorted by confidence ascending */}
          {data.price_info && data.price_info.length > 0 && (() => {
            const priceFields: (PriceInfo & { _idx: number })[] = data.price_info.map((p, i) => ({ ...p, _idx: i }));
            const sorted = sortByConfidenceAsc(priceFields, () => data.confidence_scores?.base_price);
            return (
              <section className="data-section">
                <h3>価格情報</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>項目</th>
                      <th>値</th>
                      <th>信頼度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((price) => {
                      const fieldKey = `price_${price._idx}`;
                      return (
                        <DataFieldRow
                          key={fieldKey}
                          label={price.price_type ?? `価格 ${price._idx + 1}`}
                          value={`${price.amount.toLocaleString()} ${price.currency}${price.condition ? ` (${price.condition})` : ''}`}
                          fieldKey={fieldKey}
                          confidence={data.confidence_scores?.base_price}
                          isHighlighted={highlightedField === fieldKey}
                          isManuallyEdited={manuallyEditedFields.has(fieldKey)}
                          fieldType="currency"
                          onClick={handleFieldClick}
                          onSave={async (newVal) => handleSaveField(fieldKey, newVal, 'price_info', undefined, price._idx)}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </section>
            );
          })()}

          {/* Payment methods – sorted by confidence ascending */}
          {data.payment_methods && data.payment_methods.length > 0 && (() => {
            const pmFields: (PaymentMethod & { _idx: number })[] = data.payment_methods.map((pm, i) => ({ ...pm, _idx: i }));
            const sorted = sortByConfidenceAsc(pmFields, () => data.confidence_scores?.payment_methods);
            return (
              <section className="data-section">
                <h3>支払い方法</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>項目</th>
                      <th>値</th>
                      <th>信頼度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((pm) => {
                      const fieldKey = `payment_method_${pm._idx}`;
                      const detail = pm.processing_fee
                        ? `手数料: ${pm.processing_fee}${pm.fee_type === 'percentage' ? '%' : '円'}`
                        : '';
                      return (
                        <DataFieldRow
                          key={fieldKey}
                          label={pm.method_name}
                          value={`${pm.provider ?? '—'} ${detail}`}
                          fieldKey={fieldKey}
                          confidence={data.confidence_scores?.payment_methods}
                          isHighlighted={highlightedField === fieldKey}
                          isManuallyEdited={manuallyEditedFields.has(fieldKey)}
                          fieldType="text"
                          onClick={handleFieldClick}
                          onSave={async (newVal) => handleSaveField(fieldKey, newVal, 'payment_methods', undefined, pm._idx)}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </section>
            );
          })()}

          {/* Fees – sorted by confidence ascending */}
          {data.fees && data.fees.length > 0 && (() => {
            const feeFields: (Fee & { _idx: number })[] = data.fees.map((f, i) => ({ ...f, _idx: i }));
            const sorted = sortByConfidenceAsc(feeFields, () => data.confidence_scores?.fees);
            return (
              <section className="data-section">
                <h3>手数料</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>項目</th>
                      <th>値</th>
                      <th>信頼度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((fee) => {
                      const fieldKey = `fee_${fee._idx}`;
                      return (
                        <DataFieldRow
                          key={fieldKey}
                          label={fee.fee_type}
                          value={`${fee.amount.toLocaleString()} ${fee.currency}${fee.condition ? ` (${fee.condition})` : ''}`}
                          fieldKey={fieldKey}
                          confidence={data.confidence_scores?.fees}
                          isHighlighted={highlightedField === fieldKey}
                          isManuallyEdited={manuallyEditedFields.has(fieldKey)}
                          fieldType="currency"
                          onClick={handleFieldClick}
                          onSave={async (newVal) => handleSaveField(fieldKey, newVal, 'fees', undefined, fee._idx)}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </section>
            );
          })()}

          {/* Approval workflow */}
          <ApprovalWorkflow
            extractedDataId={data.id}
            status={data.status}
            approvedBy={(data.metadata?.approved_by as string) ?? null}
            approvedAt={(data.metadata?.approved_at as string) ?? null}
            rejectionReason={(data.metadata?.rejection_reason as string) ?? null}
            onStatusChange={handleStatusChange}
          />

          {/* Change history */}
          <ChangeHistoryPanel entityId={data.id} />

          {/* Visual confirmation panel for partial/no_data extraction */}
          {visualConfirmation &&
            visualConfirmation.extraction_status !== 'complete' && (
              <section className="data-section">
                <VisualConfirmationPanel
                  crawlResultId={Number(crawlResultId)}
                  screenshotUrl={visualConfirmation.screenshot_url}
                  rawHtml={visualConfirmation.raw_html}
                  extractionStatus={visualConfirmation.extraction_status}
                  onSaved={handleVisualConfirmationSaved}
                />
              </section>
            )}
        </div>
      </div>
    </div>
  );
};

export default CrawlResultReviewPage;
