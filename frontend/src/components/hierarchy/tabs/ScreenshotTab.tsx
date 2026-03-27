import { useState, useEffect, useRef } from 'react';
import './ScreenshotTab.css';
import {
  getSiteScreenshots,
  extractData,
  getExtractedData,
  updateExtractedData,
  getScreenshotUrl,
  uploadScreenshot,
  captureScreenshot,
  deleteScreenshot,
} from '../../../services/api';
import type { Screenshot, ExtractedData } from '../../../services/api';
import { Modal } from '../../ui/Modal/Modal';
import { Button } from '../../ui/Button/Button';
import { Badge } from '../../ui/Badge/Badge';

export interface ScreenshotTabProps {
  siteId: number;
}

interface ScreenshotWithExtraction extends Screenshot {
  extractedData?: ExtractedData | null;
  isExtracting?: boolean;
  extractionError?: string | null;
}

const ScreenshotTab = ({ siteId }: ScreenshotTabProps) => {
  const [screenshots, setScreenshots] = useState<ScreenshotWithExtraction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingData, setEditingData] = useState<{ [key: number]: Record<string, any> }>({});

  // Upload modal state (always baseline overwrite)
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Capture modal state (always monitoring/violation)
  const [showCaptureModal, setShowCaptureModal] = useState(false);
  const [captureFormat, setCaptureFormat] = useState<'png' | 'pdf'>('png');
  const [capturing, setCapturing] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);

  // View modal state
  const [viewingScreenshot, setViewingScreenshot] = useState<ScreenshotWithExtraction | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const screenshotsData = await getSiteScreenshots(siteId);

      // Fetch extracted data for each screenshot
      const screenshotsWithExtraction = await Promise.all(
        screenshotsData.map(async (screenshot) => {
          try {
            const extractedData = await getExtractedData(screenshot.id);
            return { ...screenshot, extractedData };
          } catch {
            return { ...screenshot, extractedData: null };
          }
        })
      );

      setScreenshots(screenshotsWithExtraction);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'スクリーンショットの取得に失敗しました');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [siteId]);

  // Separate baseline and monitoring screenshots
  const baselineScreenshot = screenshots.find((s) => s.screenshot_type === 'baseline') || null;
  const latestMonitoring = screenshots
    .filter((s) => s.screenshot_type !== 'baseline')
    .sort((a, b) => new Date(b.crawled_at).getTime() - new Date(a.crawled_at).getTime())[0] || null;

  const handleExtractData = async (screenshotId: number) => {
    try {
      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId
            ? { ...s, isExtracting: true, extractionError: null }
            : s
        )
      );

      const extractedData = await extractData(screenshotId);

      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId
            ? { ...s, extractedData, isExtracting: false }
            : s
        )
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'データ抽出に失敗しました';
      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId
            ? { ...s, isExtracting: false, extractionError: errorMessage }
            : s
        )
      );
    }
  };

  const handleEditField = (extractedDataId: number, fieldName: string, value: any) => {
    setEditingData((prev) => ({
      ...prev,
      [extractedDataId]: {
        ...(prev[extractedDataId] || {}),
        [fieldName]: value,
      },
    }));
  };

  const handleSaveEdits = async (extractedDataId: number, screenshotId: number) => {
    try {
      const edits = editingData[extractedDataId];
      if (!edits) return;

      const screenshot = screenshots.find((s) => s.id === screenshotId);
      if (!screenshot?.extractedData) return;

      const updatedFields = {
        ...screenshot.extractedData.extracted_fields,
        ...edits,
      };

      const updatedData = await updateExtractedData(extractedDataId, {
        extracted_fields: updatedFields,
        status: 'confirmed',
      });

      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId ? { ...s, extractedData: updatedData } : s
        )
      );

      setEditingData((prev) => {
        const newState = { ...prev };
        delete newState[extractedDataId];
        return newState;
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存に失敗しました');
    }
  };

  // Re-capture: captures as monitoring (violation type in API)
  const handleReCapture = async () => {
    try {
      setCapturing(true);
      setCaptureError(null);
      await captureScreenshot(siteId, 'violation', captureFormat);
      await fetchData();
      setShowCaptureModal(false);
    } catch (err: any) {
      setCaptureError(err.response?.data?.detail || err.message || 'キャプチャに失敗しました');
    } finally {
      setCapturing(false);
    }
  };

  // Re-upload: always overwrites baseline
  const handleReUpload = async () => {
    if (!uploadFile) {
      setUploadError('ファイルを選択してください');
      return;
    }

    try {
      setUploading(true);
      setUploadError(null);

      // Delete existing baseline before uploading new one (one per site)
      if (baselineScreenshot) {
        await deleteScreenshot(baselineScreenshot.id);
      }

      await uploadScreenshot(siteId, 'baseline', uploadFile);
      await fetchData();
      closeUploadModal();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || err.message || 'アップロードに失敗しました');
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();

      if (ext !== 'png' && ext !== 'pdf') {
        setUploadError('PNG または PDF ファイルのみアップロード可能です');
        setUploadFile(null);
        return;
      }

      setUploadFile(file);
      setUploadError(null);
    }
  };

  const openUploadModal = () => {
    setUploadFile(null);
    setUploadError(null);
    setShowUploadModal(true);
  };

  const closeUploadModal = () => {
    setShowUploadModal(false);
    setUploadFile(null);
    setUploadError(null);
  };

  const openCaptureModal = () => {
    setCaptureFormat('png');
    setCaptureError(null);
    setShowCaptureModal(true);
  };

  const closeCaptureModal = () => {
    setShowCaptureModal(false);
    setCaptureError(null);
  };

  const getTypeLabel = (type: string): string => {
    return type === 'baseline' ? 'ベースライン' : 'モニタリング';
  };

  const getTypeBadge = (type: string) => {
    if (type === 'baseline') {
      return <Badge variant="info" size="sm">ベースライン</Badge>;
    }
    return <Badge variant="neutral" size="sm">モニタリング</Badge>;
  };

  const renderScreenshotCard = (screenshot: ScreenshotWithExtraction) => (
    <div key={screenshot.id} className="screenshot-item">
      <div className="screenshot-header">
        <div className="screenshot-info">
          {getTypeBadge(screenshot.screenshot_type)}
          <span className="screenshot-format">{screenshot.file_format.toUpperCase()}</span>
          <span className="screenshot-date">
            {new Date(screenshot.crawled_at).toLocaleString('ja-JP')}
          </span>
        </div>
      </div>

      {/* Thumbnail */}
      {screenshot.file_format === 'png' && (
        <div
          className="screenshot-thumbnail"
          onClick={() => setViewingScreenshot(screenshot)}
          style={{ cursor: 'pointer' }}
        >
          <img
            src={getScreenshotUrl(screenshot.id)}
            alt={`${screenshot.site_name} - ${getTypeLabel(screenshot.screenshot_type)}`}
            loading="lazy"
          />
        </div>
      )}

      {screenshot.file_format === 'pdf' && (
        <div
          className="screenshot-thumbnail pdf-placeholder"
          onClick={() => setViewingScreenshot(screenshot)}
          style={{ cursor: 'pointer' }}
        >
          <span>📄 PDF</span>
        </div>
      )}

      {/* Extract Data Button */}
      <div className="screenshot-actions">
        <button
          className="extract-button"
          onClick={() => handleExtractData(screenshot.id)}
          disabled={screenshot.isExtracting || !!screenshot.extractedData}
        >
          {screenshot.isExtracting ? (
            <>
              <span className="spinner">⟳</span>
              <span>抽出中...</span>
            </>
          ) : screenshot.extractedData ? (
            'データ抽出済み'
          ) : (
            'データ抽出'
          )}
        </button>
      </div>

      {/* Extraction Progress */}
      {screenshot.isExtracting && (
        <div className="extraction-progress">
          <div className="progress-bar">
            <div className="progress-bar-fill"></div>
          </div>
          <p>データ抽出が実行中です...</p>
        </div>
      )}

      {/* Extraction Error */}
      {screenshot.extractionError && (
        <div className="extraction-error">
          <p>エラー: {screenshot.extractionError}</p>
        </div>
      )}

      {/* Extracted Data Preview and Edit */}
      {screenshot.extractedData && (
        <div className="extracted-data">
          <h4>抽出データ</h4>
          <div className="extracted-fields">
            {Object.entries(screenshot.extractedData.extracted_fields).map(
              ([fieldName, value]) => {
                const confidence =
                  screenshot.extractedData!.confidence_scores[fieldName];
                const isEditing = editingData[screenshot.extractedData!.id]?.[fieldName] !== undefined;
                const editValue = isEditing
                  ? editingData[screenshot.extractedData!.id][fieldName]
                  : value;

                return (
                  <div key={fieldName} className="field-item">
                    <label className="field-label">{fieldName}</label>
                    <div className="field-value-container">
                      <input
                        type="text"
                        className="field-input"
                        value={editValue?.toString() || ''}
                        onChange={(e) =>
                          handleEditField(
                            screenshot.extractedData!.id,
                            fieldName,
                            e.target.value
                          )
                        }
                      />
                      {confidence !== undefined && (
                        <span className="confidence-score">
                          信頼度: {(confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  </div>
                );
              }
            )}
          </div>

          {editingData[screenshot.extractedData.id] && (
            <div className="extracted-data-actions">
              <button
                className="save-button"
                onClick={() =>
                  handleSaveEdits(screenshot.extractedData!.id, screenshot.id)
                }
              >
                保存
              </button>
              <button
                className="cancel-button"
                onClick={() => {
                  setEditingData((prev) => {
                    const newState = { ...prev };
                    delete newState[screenshot.extractedData!.id];
                    return newState;
                  });
                }}
              >
                キャンセル
              </button>
            </div>
          )}

          <div className="extracted-data-status">
            <span className={`status-badge status-${screenshot.extractedData.status}`}>
              {screenshot.extractedData.status === 'pending'
                ? '確認待ち'
                : screenshot.extractedData.status === 'confirmed'
                ? '確認済み'
                : '却下'}
            </span>
          </div>
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="tab-loading">
        <span className="spinner">⟳</span>
        <span>読み込み中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <p>エラー: {error}</p>
      </div>
    );
  }

  return (
    <div className="screenshot-tab">
      {/* Baseline Section */}
      <div className="screenshot-section" data-testid="baseline-section">
        <div className="screenshot-section-header">
          <h3>ベースラインスクリーンショット</h3>
          <div className="screenshot-section-actions">
            <Button variant="secondary" size="sm" onClick={openUploadModal}>
              📤 再アップロード
            </Button>
          </div>
        </div>
        {baselineScreenshot ? (
          renderScreenshotCard(baselineScreenshot)
        ) : (
          <div className="tab-empty">
            <p>ベースラインスクリーンショットがありません</p>
            <Button variant="primary" size="sm" onClick={openUploadModal}>
              📤 アップロード
            </Button>
          </div>
        )}
      </div>

      {/* Latest Monitoring Section */}
      <div className="screenshot-section" data-testid="monitoring-section">
        <div className="screenshot-section-header">
          <h3>最新モニタリングキャプチャ</h3>
          <div className="screenshot-section-actions">
            <Button variant="primary" size="sm" onClick={openCaptureModal}>
              📸 再キャプチャ
            </Button>
          </div>
        </div>
        {latestMonitoring ? (
          renderScreenshotCard(latestMonitoring)
        ) : (
          <div className="tab-empty">
            <p>モニタリングキャプチャがありません</p>
            <Button variant="primary" size="sm" onClick={openCaptureModal}>
              📸 キャプチャ
            </Button>
          </div>
        )}
      </div>

      {/* Upload Modal — no type selector, always baseline overwrite */}
      <Modal
        isOpen={showUploadModal}
        onClose={closeUploadModal}
        title="ベースラインスクリーンショットのアップロード"
        size="md"
        footer={
          <>
            <Button variant="secondary" size="md" onClick={closeUploadModal} disabled={uploading}>
              キャンセル
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleReUpload}
              disabled={uploading || !uploadFile}
              loading={uploading}
            >
              アップロード
            </Button>
          </>
        }
      >
        <div className="upload-form">
          <p className="upload-notice">
            アップロードしたファイルはベースラインスクリーンショットとして保存されます。
            既存のベースラインは上書きされます。
          </p>
          <div className="form-group">
            <label htmlFor="upload_file">ファイル (PNG または PDF) *</label>
            <input
              ref={fileInputRef}
              type="file"
              id="upload_file"
              accept=".png,.pdf"
              onChange={handleFileChange}
              required
            />
            {uploadFile && (
              <p className="file-info">選択: {uploadFile.name}</p>
            )}
          </div>
          {uploadError && (
            <div className="form-error">{uploadError}</div>
          )}
        </div>
      </Modal>

      {/* Capture Modal — no type selector, always monitoring */}
      <Modal
        isOpen={showCaptureModal}
        onClose={closeCaptureModal}
        title="モニタリングキャプチャ"
        size="md"
        footer={
          <>
            <Button variant="secondary" size="md" onClick={closeCaptureModal} disabled={capturing}>
              キャンセル
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={handleReCapture}
              disabled={capturing}
              loading={capturing}
            >
              キャプチャ実行
            </Button>
          </>
        }
      >
        <div className="upload-form">
          <p className="upload-notice">
            サイトの現在の状態をキャプチャします。モニタリングキャプチャとして保存されます。
          </p>
          <div className="form-group">
            <label htmlFor="capture_format">ファイル形式 *</label>
            <select
              id="capture_format"
              value={captureFormat}
              onChange={(e) => setCaptureFormat(e.target.value as 'png' | 'pdf')}
              required
            >
              <option value="png">PNG (画像)</option>
              <option value="pdf">PDF (文書)</option>
            </select>
          </div>
          {captureError && (
            <div className="form-error">{captureError}</div>
          )}
        </div>
      </Modal>

      {/* View Modal */}
      <Modal
        isOpen={!!viewingScreenshot}
        onClose={() => setViewingScreenshot(null)}
        title={viewingScreenshot?.site_name ?? ''}
        size="lg"
        footer={
          <Button variant="secondary" size="md" onClick={() => setViewingScreenshot(null)}>
            閉じる
          </Button>
        }
      >
        {viewingScreenshot && (
          <>
            <div className="screenshot-view-subtitle">
              {getTypeBadge(viewingScreenshot.screenshot_type)}
              <span className="screenshot-format">{viewingScreenshot.file_format.toUpperCase()}</span>
              <span className="screenshot-date">
                {new Date(viewingScreenshot.crawled_at).toLocaleString('ja-JP')}
              </span>
            </div>
            <div className="screenshot-viewer">
              {viewingScreenshot.file_format === 'png' ? (
                <img
                  src={getScreenshotUrl(viewingScreenshot.id)}
                  alt={`${viewingScreenshot.site_name} - ${getTypeLabel(viewingScreenshot.screenshot_type)}`}
                />
              ) : (
                <iframe
                  src={getScreenshotUrl(viewingScreenshot.id)}
                  style={{ width: '100%', height: '600px', border: 'none' }}
                  title="PDF Viewer"
                />
              )}
            </div>
          </>
        )}
      </Modal>
    </div>
  );
};

export default ScreenshotTab;
