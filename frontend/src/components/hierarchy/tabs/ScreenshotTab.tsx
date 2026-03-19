import { useState, useEffect } from 'react';
import {
  getSiteScreenshots,
  extractData,
  getExtractedData,
  updateExtractedData,
  getScreenshotUrl,
} from '../../../services/api';
import type { Screenshot, ExtractedData } from '../../../services/api';

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

  useEffect(() => {
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
              // No extracted data yet
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

    fetchData();
  }, [siteId]);

  const handleExtractData = async (screenshotId: number) => {
    try {
      // Set extracting state
      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId
            ? { ...s, isExtracting: true, extractionError: null }
            : s
        )
      );

      const extractedData = await extractData(screenshotId);

      // Update screenshot with extracted data
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

      // Update screenshot with new extracted data
      setScreenshots((prev) =>
        prev.map((s) =>
          s.id === screenshotId ? { ...s, extractedData: updatedData } : s
        )
      );

      // Clear editing state
      setEditingData((prev) => {
        const newState = { ...prev };
        delete newState[extractedDataId];
        return newState;
      });
    } catch (err) {
      alert(err instanceof Error ? err.message : '保存に失敗しました');
    }
  };

  const getTypeLabel = (type: string): string => {
    return type === 'baseline' ? '初期状態' : '異常状態';
  };

  const getFormatLabel = (format: string): string => {
    return format.toUpperCase();
  };

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

  if (screenshots.length === 0) {
    return (
      <div className="tab-empty">
        <p>スクリーンショットがありません</p>
      </div>
    );
  }

  return (
    <div className="screenshot-tab">
      {screenshots.map((screenshot) => (
        <div key={screenshot.id} className="screenshot-item">
          <div className="screenshot-header">
            <div className="screenshot-info">
              <span className="screenshot-type">{getTypeLabel(screenshot.screenshot_type)}</span>
              <span className="screenshot-format">{getFormatLabel(screenshot.file_format)}</span>
              <span className="screenshot-date">
                {new Date(screenshot.crawled_at).toLocaleString('ja-JP')}
              </span>
            </div>
          </div>

          {/* Thumbnail */}
          {screenshot.file_format === 'png' && (
            <div className="screenshot-thumbnail">
              <img
                src={getScreenshotUrl(screenshot.id)}
                alt={`${screenshot.site_name} - ${getTypeLabel(screenshot.screenshot_type)}`}
                loading="lazy"
              />
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

          {/* Extraction Progress Indicator */}
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

              {/* Save Button */}
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
      ))}
    </div>
  );
};

export default ScreenshotTab;
