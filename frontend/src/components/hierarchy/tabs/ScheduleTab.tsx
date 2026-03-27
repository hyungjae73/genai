import { useState, useEffect, useCallback } from 'react';
import {
  getSchedule,
  createSchedule,
  updateSchedule,
  updateSiteSettings,
} from '../../../api/schedules';
import type {
  CrawlScheduleData,
  UpdateSiteSettingsRequest,
} from '../../../api/schedules';
import { triggerCrawl } from '../../../services/api';
import './ScheduleTab.css';

interface ScheduleTabProps {
  siteId: number;
}

interface PluginInfo {
  name: string;
  label: string;
  defaultEnabled: boolean;
}

const ALL_PLUGINS: PluginInfo[] = [
  { name: 'LocalePlugin', label: 'ロケール設定（ja-JP）', defaultEnabled: true },
  { name: 'PreCaptureScriptPlugin', label: 'プレキャプチャスクリプト実行', defaultEnabled: true },
  { name: 'ModalDismissPlugin', label: 'モーダル自動閉じ', defaultEnabled: true },
  { name: 'StructuredDataPlugin', label: '構造化データ抽出', defaultEnabled: true },
  { name: 'ShopifyPlugin', label: 'Shopify API価格取得', defaultEnabled: true },
  { name: 'HTMLParserPlugin', label: 'HTMLフォールバック抽出', defaultEnabled: true },
  { name: 'OCRPlugin', label: 'OCRテキスト抽出', defaultEnabled: true },
  { name: 'ContractComparisonPlugin', label: '契約条件比較', defaultEnabled: true },
  { name: 'EvidencePreservationPlugin', label: '証拠保全', defaultEnabled: true },
  { name: 'DBStoragePlugin', label: 'DB保存', defaultEnabled: true },
  { name: 'ObjectStoragePlugin', label: 'オブジェクトストレージ', defaultEnabled: true },
  { name: 'AlertPlugin', label: 'アラート生成', defaultEnabled: true },
];

/**
 * Compute effective toggle state for each plugin given global defaults and site-level plugin_config.
 */
export function computeEffectivePluginStates(
  plugins: PluginInfo[],
  pluginConfig: Record<string, unknown> | null,
): Record<string, boolean> {
  const states: Record<string, boolean> = {};
  for (const plugin of plugins) {
    states[plugin.name] = plugin.defaultEnabled;
  }

  if (!pluginConfig) return states;

  const disabled = (pluginConfig.disabled as string[]) || [];
  const enabled = (pluginConfig.enabled as string[]) || [];

  for (const name of disabled) {
    if (name in states) {
      states[name] = false;
    }
  }
  for (const name of enabled) {
    if (name in states) {
      states[name] = true;
    }
  }

  return states;
}

const PRE_CAPTURE_PLACEHOLDER = '[{"action": "click", "selector": ".lang-ja", "label": "日本語選択"}]';

const ScheduleTab = ({ siteId }: ScheduleTabProps) => {
  const [schedule, setSchedule] = useState<CrawlScheduleData | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Schedule form state
  const [priority, setPriority] = useState<'high' | 'normal' | 'low'>('normal');
  const [intervalMinutes, setIntervalMinutes] = useState(1440);

  // PreCaptureScript state
  const [preCaptureScript, setPreCaptureScript] = useState('');
  const [scriptError, setScriptError] = useState<string | null>(null);

  // Plugin settings state
  const [pluginSectionOpen, setPluginSectionOpen] = useState(false);
  const [pluginConfig, setPluginConfig] = useState<Record<string, unknown> | null>(null);
  const [pluginStates, setPluginStates] = useState<Record<string, boolean>>({});

  const loadSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSchedule(siteId);
      setSchedule(data);
      setIsNew(false);
      setPriority(data.priority);
      setIntervalMinutes(data.interval_minutes);
    } catch {
      // No schedule exists — show create form with defaults
      setSchedule(null);
      setIsNew(true);
      setPriority('normal');
      setIntervalMinutes(1440);
    } finally {
      setLoading(false);
    }
  }, [siteId]);

  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);

  useEffect(() => {
    setPluginStates(computeEffectivePluginStates(ALL_PLUGINS, pluginConfig));
  }, [pluginConfig]);

  const validateJson = (value: string): boolean => {
    if (!value.trim()) return true;
    try {
      JSON.parse(value);
      setScriptError(null);
      return true;
    } catch {
      setScriptError('JSON形式が不正です');
      return false;
    }
  };

  const handleSave = async () => {
    if (!validateJson(preCaptureScript)) return;

    setSaving(true);
    setError(null);
    try {
      if (isNew) {
        const data = await createSchedule(siteId, { priority, interval_minutes: intervalMinutes });
        setSchedule(data);
        setIsNew(false);
      } else {
        const data = await updateSchedule(siteId, { priority, interval_minutes: intervalMinutes });
        setSchedule(data);
      }

      // Update site settings (pre_capture_script, plugin_config)
      const siteUpdate: UpdateSiteSettingsRequest = {};
      const scriptValue = preCaptureScript.trim();
      siteUpdate.pre_capture_script = scriptValue ? JSON.parse(scriptValue) : null;
      siteUpdate.plugin_config = pluginConfig;
      siteUpdate.crawl_priority = priority;
      await updateSiteSettings(siteId, siteUpdate);
    } catch {
      setError('保存に失敗しました');
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    try {
      await triggerCrawl(siteId);
    } catch {
      setError('即時実行に失敗しました');
    }
  };

  const handlePluginToggle = (pluginName: string, enabled: boolean) => {
    const newStates = { ...pluginStates, [pluginName]: enabled };
    setPluginStates(newStates);

    // Convert toggle states to plugin_config JSON
    const disabled: string[] = [];
    const enabledList: string[] = [];
    for (const plugin of ALL_PLUGINS) {
      const isEnabled = newStates[plugin.name];
      if (plugin.defaultEnabled && !isEnabled) {
        disabled.push(plugin.name);
      } else if (!plugin.defaultEnabled && isEnabled) {
        enabledList.push(plugin.name);
      }
    }

    if (disabled.length === 0 && enabledList.length === 0) {
      setPluginConfig(null);
    } else {
      setPluginConfig({
        disabled,
        enabled: enabledList,
        params: (pluginConfig as Record<string, unknown>)?.params || {},
      });
    }
  };

  const handleResetPlugins = () => {
    setPluginConfig(null);
    setPluginStates(computeEffectivePluginStates(ALL_PLUGINS, null));
  };

  const isGlobalDefault = pluginConfig === null;

  if (loading) {
    return <div className="schedule-tab">読み込み中...</div>;
  }

  return (
    <div className="schedule-tab">
      {error && <div className="schedule-error">{error}</div>}

      {/* Schedule Info Section */}
      <section className="schedule-section">
        <h3>スケジュール情報</h3>
        <div className="schedule-form">
          <div className="form-row">
            <label htmlFor="priority">優先度</label>
            <select
              id="priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value as 'high' | 'normal' | 'low')}
            >
              <option value="high">高</option>
              <option value="normal">通常</option>
              <option value="low">低</option>
            </select>
          </div>

          <div className="form-row">
            <label htmlFor="interval">クロール間隔（分）</label>
            <input
              id="interval"
              type="number"
              min={1}
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
            />
          </div>

          <div className="form-row">
            <label>次回クロール予定</label>
            <span className="read-only-value" data-testid="next-crawl-time">
              {schedule?.next_crawl_at
                ? new Date(schedule.next_crawl_at).toLocaleString('ja-JP')
                : '未設定'}
            </span>
          </div>

          <button
            type="button"
            className="run-now-button"
            onClick={handleRunNow}
          >
            今すぐ実行
          </button>
        </div>
      </section>

      {/* Delta Crawl Info Section */}
      <section className="schedule-section">
        <h3>デルタクロール情報</h3>
        <div className="delta-info">
          <div className="form-row">
            <label>ETag</label>
            <span className="read-only-value" data-testid="etag-value">
              {schedule?.last_etag || '未取得'}
            </span>
          </div>
          <div className="form-row">
            <label>Last-Modified</label>
            <span className="read-only-value" data-testid="last-modified-value">
              {schedule?.last_modified || '未取得'}
            </span>
          </div>
        </div>
      </section>

      {/* PreCaptureScript Editor Section */}
      <section className="schedule-section">
        <h3>プレキャプチャスクリプト</h3>
        <div className="script-editor">
          <textarea
            data-testid="pre-capture-script"
            value={preCaptureScript}
            onChange={(e) => {
              setPreCaptureScript(e.target.value);
              if (scriptError) validateJson(e.target.value);
            }}
            placeholder={PRE_CAPTURE_PLACEHOLDER}
            rows={6}
          />
          {scriptError && (
            <div className="validation-error" data-testid="script-error">
              {scriptError}
            </div>
          )}
        </div>
      </section>

      {/* Plugin Settings (Advanced) Section */}
      <section className="schedule-section plugin-section">
        <button
          type="button"
          className="section-toggle"
          onClick={() => setPluginSectionOpen(!pluginSectionOpen)}
          aria-expanded={pluginSectionOpen}
        >
          <span className="toggle-icon">{pluginSectionOpen ? '▼' : '▶'}</span>
          プラグイン設定（上級）
        </button>

        {pluginSectionOpen && (
          <div className="plugin-settings" data-testid="plugin-settings">
            {isGlobalDefault && (
              <p className="global-default-notice">グローバル設定に従う</p>
            )}
            <ul className="plugin-list">
              {ALL_PLUGINS.map((plugin) => (
                <li key={plugin.name} className="plugin-item">
                  <label className="plugin-toggle-label">
                    <input
                      type="checkbox"
                      role="switch"
                      checked={pluginStates[plugin.name] ?? plugin.defaultEnabled}
                      onChange={(e) => handlePluginToggle(plugin.name, e.target.checked)}
                    />
                    <span className="plugin-name">{plugin.name}</span>
                  </label>
                  <span className="plugin-description">{plugin.label}</span>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="reset-button"
              onClick={handleResetPlugins}
            >
              デフォルトに戻す
            </button>
          </div>
        )}
      </section>

      {/* Save Button */}
      <div className="schedule-actions">
        <button
          type="button"
          className="save-button"
          onClick={handleSave}
          disabled={saving || !!scriptError}
        >
          {saving ? '保存中...' : '保存'}
        </button>
      </div>
    </div>
  );
};

export default ScheduleTab;
