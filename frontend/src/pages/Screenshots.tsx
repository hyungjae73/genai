import { useEffect, useState } from 'react';
import { getSites, getSiteScreenshots, uploadScreenshot, deleteScreenshot, getScreenshotUrl, type Site, type Screenshot } from '../services/api';

const Screenshots = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  
  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadSiteId, setUploadSiteId] = useState<number>(0);
  const [uploadType, setUploadType] = useState<'baseline' | 'violation'>('baseline');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  // Capture modal state
  const [showCaptureModal, setShowCaptureModal] = useState(false);
  const [captureSiteId, setCaptureSiteId] = useState<number>(0);
  const [captureType, setCaptureType] = useState<'baseline' | 'violation'>('baseline');
  const [captureFormat, setCaptureFormat] = useState<'png' | 'pdf'>('png');
  const [capturing, setCapturing] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  
  // View modal state
  const [viewingScreenshot, setViewingScreenshot] = useState<Screenshot | null>(null);

  useEffect(() => {
    fetchSites();
  }, []);

  useEffect(() => {
    if (selectedSite) {
      fetchScreenshots(selectedSite);
    }
  }, [selectedSite, typeFilter]);

  const fetchSites = async () => {
    try {
      setLoading(true);
      const data = await getSites();
      setSites(data);
      setError(null);
    } catch (err) {
      setError('サイト一覧の取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchScreenshots = async (siteId: number) => {
    try {
      setLoading(true);
      const filterType = typeFilter === 'all' ? undefined : (typeFilter as 'baseline' | 'violation');
      const data = await getSiteScreenshots(siteId, filterType);
      setScreenshots(data);
      setError(null);
    } catch (err) {
      setError('スクリーンショットの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const openUploadModal = (siteId?: number) => {
    setUploadSiteId(siteId || (sites.length > 0 ? sites[0].id : 0));
    setUploadType('baseline');
    setUploadFile(null);
    setUploadError(null);
    setShowUploadModal(true);
  };

  const closeUploadModal = () => {
    setShowUploadModal(false);
    setUploadFile(null);
    setUploadError(null);
  };

  const openCaptureModal = (siteId?: number) => {
    setCaptureSiteId(siteId || (sites.length > 0 ? sites[0].id : 0));
    setCaptureType('baseline');
    setCaptureFormat('png');
    setCaptureError(null);
    setShowCaptureModal(true);
  };

  const closeCaptureModal = () => {
    setShowCaptureModal(false);
    setCaptureError(null);
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

  const handleUpload = async () => {
    if (!uploadFile) {
      setUploadError('ファイルを選択してください');
      return;
    }
    
    if (uploadSiteId === 0) {
      setUploadError('サイトを選択してください');
      return;
    }

    try {
      setUploading(true);
      await uploadScreenshot(uploadSiteId, uploadType, uploadFile);
      
      if (selectedSite === uploadSiteId) {
        await fetchScreenshots(uploadSiteId);
      }
      
      closeUploadModal();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'アップロードに失敗しました');
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const handleCapture = async () => {
    if (captureSiteId === 0) {
      setCaptureError('サイトを選択してください');
      return;
    }

    try {
      setCapturing(true);
      await captureScreenshot(captureSiteId, captureType, captureFormat);
      
      if (selectedSite === captureSiteId) {
        await fetchScreenshots(captureSiteId);
      }
      
      closeCaptureModal();
    } catch (err: any) {
      setCaptureError(err.response?.data?.detail || 'キャプチャに失敗しました');
      console.error(err);
    } finally {
      setCapturing(false);
    }
  };

  const handleDelete = async (screenshot: Screenshot) => {
    if (!confirm(`このスクリーンショットを削除してもよろしいですか？`)) {
      return;
    }

    try {
      await deleteScreenshot(screenshot.id);
      if (selectedSite) {
        await fetchScreenshots(selectedSite);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || '削除に失敗しました');
      console.error(err);
    }
  };

  const openViewer = (screenshot: Screenshot) => {
    setViewingScreenshot(screenshot);
  };

  const closeViewer = () => {
    setViewingScreenshot(null);
  };

  const getTypeBadge = (type: string) => {
    const typeMap: Record<string, { label: string; className: string }> = {
      baseline: { label: '初期状態', className: 'type-baseline' },
      violation: { label: '異常状態', className: 'type-violation' },
    };
    const typeInfo = typeMap[type] || { label: type, className: '' };
    return <span className={`type-badge ${typeInfo.className}`}>{typeInfo.label}</span>;
  };

  if (loading && sites.length === 0) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error && sites.length === 0) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="screenshots">
      <div className="page-header">
        <h1>スクリーンショット管理</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-primary" onClick={() => openCaptureModal()}>
            📸 ページをキャプチャ
          </button>
          <button className="btn btn-secondary" onClick={() => openUploadModal()}>
            📤 ファイルアップロード
          </button>
        </div>
      </div>

      <div className="filters">
        <select
          value={selectedSite || ''}
          onChange={(e) => setSelectedSite(e.target.value ? Number(e.target.value) : null)}
          className="site-filter"
        >
          <option value="">サイトを選択</option>
          {sites.map(site => (
            <option key={site.id} value={site.id}>{site.name}</option>
          ))}
        </select>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="type-filter"
        >
          <option value="all">すべてのタイプ</option>
          <option value="baseline">初期状態</option>
          <option value="violation">異常状態</option>
        </select>
      </div>

      {selectedSite ? (
        <div className="screenshots-grid">
          {screenshots.map(screenshot => (
            <div key={screenshot.id} className="screenshot-card">
              <div className="screenshot-preview" onClick={() => openViewer(screenshot)}>
                {screenshot.file_format === 'png' ? (
                  <img 
                    src={getScreenshotUrl(screenshot.id)} 
                    alt={`${screenshot.site_name} - ${screenshot.screenshot_type}`}
                  />
                ) : (
                  <div className="pdf-preview">
                    <span className="pdf-icon">📄</span>
                    <span>PDF</span>
                  </div>
                )}
              </div>
              
              <div className="screenshot-info">
                <div className="screenshot-header">
                  {getTypeBadge(screenshot.screenshot_type)}
                  <span className="screenshot-format">{screenshot.file_format.toUpperCase()}</span>
                </div>
                <p className="screenshot-site">{screenshot.site_name}</p>
                <p className="screenshot-date">
                  {new Date(screenshot.crawled_at).toLocaleString('ja-JP')}
                </p>
                <div className="screenshot-actions">
                  <button 
                    className="btn btn-sm btn-secondary" 
                    onClick={() => openViewer(screenshot)}
                  >
                    表示
                  </button>
                  <button 
                    className="btn btn-sm btn-danger" 
                    onClick={() => handleDelete(screenshot)}
                  >
                    削除
                  </button>
                </div>
              </div>
            </div>
          ))}
          
          {screenshots.length === 0 && (
            <div className="no-data">スクリーンショットがありません</div>
          )}
        </div>
      ) : (
        <div className="no-selection">
          <p>サイトを選択してスクリーンショットを表示してください</p>
        </div>
      )}

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={closeUploadModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>スクリーンショットアップロード</h2>
              <button className="modal-close" onClick={closeUploadModal}>×</button>
            </div>

            <div className="upload-form">
              <div className="form-group">
                <label htmlFor="upload_site">サイト *</label>
                <select
                  id="upload_site"
                  value={uploadSiteId}
                  onChange={(e) => setUploadSiteId(Number(e.target.value))}
                  required
                >
                  <option value={0}>サイトを選択</option>
                  {sites.map(site => (
                    <option key={site.id} value={site.id}>{site.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="upload_type">タイプ *</label>
                <select
                  id="upload_type"
                  value={uploadType}
                  onChange={(e) => setUploadType(e.target.value as 'baseline' | 'violation')}
                  required
                >
                  <option value="baseline">初期状態</option>
                  <option value="violation">異常状態</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="upload_file">ファイル (PNG または PDF) *</label>
                <input
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

              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={closeUploadModal}
                  disabled={uploading}
                >
                  キャンセル
                </button>
                <button 
                  type="button" 
                  className="btn btn-primary"
                  onClick={handleUpload}
                  disabled={uploading || !uploadFile}
                >
                  {uploading ? 'アップロード中...' : 'アップロード'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Capture Modal */}
      {showCaptureModal && (
        <div className="modal-overlay" onClick={closeCaptureModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>ページキャプチャ</h2>
              <button className="modal-close" onClick={closeCaptureModal}>×</button>
            </div>

            <div className="upload-form">
              <div className="form-group">
                <label htmlFor="capture_site">サイト *</label>
                <select
                  id="capture_site"
                  value={captureSiteId}
                  onChange={(e) => setCaptureSiteId(Number(e.target.value))}
                  required
                >
                  <option value={0}>サイトを選択</option>
                  {sites.map(site => (
                    <option key={site.id} value={site.id}>{site.name}</option>
                  ))}
                </select>
                {captureSiteId > 0 && (
                  <p className="file-info">
                    URL: {sites.find(s => s.id === captureSiteId)?.url}
                  </p>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="capture_type">タイプ *</label>
                <select
                  id="capture_type"
                  value={captureType}
                  onChange={(e) => setCaptureType(e.target.value as 'baseline' | 'violation')}
                  required
                >
                  <option value="baseline">初期状態</option>
                  <option value="violation">異常状態</option>
                </select>
              </div>

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

              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={closeCaptureModal}
                  disabled={capturing}
                >
                  キャンセル
                </button>
                <button 
                  type="button" 
                  className="btn btn-primary"
                  onClick={handleCapture}
                  disabled={capturing || captureSiteId === 0}
                >
                  {capturing ? 'キャプチャ中...' : 'キャプチャ実行'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* View Modal */}
      {viewingScreenshot && (
        <div className="modal-overlay" onClick={closeViewer}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{viewingScreenshot.site_name}</h2>
                <div style={{ display: 'flex', gap: '10px', marginTop: '5px' }}>
                  {getTypeBadge(viewingScreenshot.screenshot_type)}
                  <span className="screenshot-format">{viewingScreenshot.file_format.toUpperCase()}</span>
                </div>
              </div>
              <button className="modal-close" onClick={closeViewer}>×</button>
            </div>

            <div className="screenshot-viewer">
              {viewingScreenshot.file_format === 'png' ? (
                <img 
                  src={getScreenshotUrl(viewingScreenshot.id)} 
                  alt={`${viewingScreenshot.site_name} - ${viewingScreenshot.screenshot_type}`}
                  style={{ width: '100%', height: 'auto' }}
                />
              ) : (
                <iframe
                  src={getScreenshotUrl(viewingScreenshot.id)}
                  style={{ width: '100%', height: '600px', border: 'none' }}
                  title="PDF Viewer"
                />
              )}
            </div>

            <div className="modal-footer">
              <p className="screenshot-date">
                撮影日時: {new Date(viewingScreenshot.crawled_at).toLocaleString('ja-JP')}
              </p>
              <button className="btn btn-secondary" onClick={closeViewer}>
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Screenshots;
