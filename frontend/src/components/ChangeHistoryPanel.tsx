import React, { useEffect, useState } from 'react';
import { fetchAuditLogs } from '../api/extractedData';
import type { AuditLogEntry } from '../types/extractedData';

/* ------------------------------------------------------------------ */
/*  ChangeHistoryPanel – collapsible audit log viewer                  */
/* ------------------------------------------------------------------ */

export interface ChangeHistoryPanelProps {
  /** Entity ID (extracted_payment_info id) */
  entityId: number;
  /** Entity type for the audit log endpoint */
  entityType?: string;
  /** Optional: filter to a specific field name */
  fieldFilter?: string;
}

const ChangeHistoryPanel: React.FC<ChangeHistoryPanelProps> = ({
  entityId,
  entityType = 'extracted_payment_info',
  fieldFilter,
}) => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [selectedField, setSelectedField] = useState<string | null>(fieldFilter ?? null);

  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const result = await fetchAuditLogs(entityType, entityId);
        if (!cancelled) setLogs(result);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [entityId, entityType, expanded]);

  // Derive unique field names for the field filter
  const fieldNames = Array.from(new Set(logs.map((l) => l.field_name))).sort();

  const filteredLogs = selectedField
    ? logs.filter((l) => l.field_name === selectedField)
    : logs;

  return (
    <div
      className="change-history-panel"
      style={{
        border: '1px solid var(--border-color, #e5e7eb)',
        borderRadius: '8px',
        marginTop: '1rem',
      }}
    >
      {/* Collapsible header */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
        aria-controls="change-history-content"
        style={{
          width: '100%',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.6rem 1rem',
          background: 'var(--bg-color, #f9fafb)',
          border: 'none',
          borderRadius: expanded ? '8px 8px 0 0' : '8px',
          cursor: 'pointer',
          fontSize: '0.9rem',
          fontWeight: 600,
          color: 'var(--text-primary, #111827)',
        }}
      >
        <span>📋 変更履歴</span>
        <span style={{ fontSize: '0.75rem' }}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div id="change-history-content" style={{ padding: '0.75rem 1rem' }}>
          {loading && <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #6b7280)' }}>読み込み中...</p>}

          {!loading && logs.length === 0 && (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #6b7280)' }}>
              変更履歴はありません
            </p>
          )}

          {!loading && logs.length > 0 && (
            <>
              {/* Field filter */}
              {fieldNames.length > 1 && (
                <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #6b7280)' }}>フィールド:</span>
                  <button
                    type="button"
                    onClick={() => setSelectedField(null)}
                    style={{
                      padding: '0.15rem 0.4rem',
                      fontSize: '0.7rem',
                      borderRadius: '4px',
                      border: '1px solid var(--border-color, #e5e7eb)',
                      backgroundColor: selectedField === null ? 'var(--primary-color, #2563eb)' : 'transparent',
                      color: selectedField === null ? '#fff' : 'var(--text-secondary, #6b7280)',
                      cursor: 'pointer',
                    }}
                  >
                    すべて
                  </button>
                  {fieldNames.map((fn) => (
                    <button
                      key={fn}
                      type="button"
                      onClick={() => setSelectedField(fn)}
                      style={{
                        padding: '0.15rem 0.4rem',
                        fontSize: '0.7rem',
                        borderRadius: '4px',
                        border: '1px solid var(--border-color, #e5e7eb)',
                        backgroundColor: selectedField === fn ? 'var(--primary-color, #2563eb)' : 'transparent',
                        color: selectedField === fn ? '#fff' : 'var(--text-secondary, #6b7280)',
                        cursor: 'pointer',
                      }}
                    >
                      {fn}
                    </button>
                  ))}
                </div>
              )}

              {/* Log entries */}
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', borderBottom: '2px solid var(--border-color, #e5e7eb)', color: 'var(--text-secondary, #6b7280)', fontWeight: 600 }}>日時</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', borderBottom: '2px solid var(--border-color, #e5e7eb)', color: 'var(--text-secondary, #6b7280)', fontWeight: 600 }}>ユーザー</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', borderBottom: '2px solid var(--border-color, #e5e7eb)', color: 'var(--text-secondary, #6b7280)', fontWeight: 600 }}>フィールド</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', borderBottom: '2px solid var(--border-color, #e5e7eb)', color: 'var(--text-secondary, #6b7280)', fontWeight: 600 }}>旧値</th>
                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', borderBottom: '2px solid var(--border-color, #e5e7eb)', color: 'var(--text-secondary, #6b7280)', fontWeight: 600 }}>新値</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLogs.map((log) => (
                    <tr key={log.id}>
                      <td style={{ padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--border-color, #e5e7eb)', whiteSpace: 'nowrap' }}>
                        {new Date(log.timestamp).toLocaleString('ja-JP')}
                      </td>
                      <td style={{ padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--border-color, #e5e7eb)' }}>
                        {log.user}
                      </td>
                      <td style={{ padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--border-color, #e5e7eb)', fontWeight: 500 }}>
                        {log.field_name}
                      </td>
                      <td style={{ padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--border-color, #e5e7eb)', color: 'var(--danger-color, #ef4444)', textDecoration: 'line-through' }}>
                        {log.old_value ?? '—'}
                      </td>
                      <td style={{ padding: '0.35rem 0.5rem', borderBottom: '1px solid var(--border-color, #e5e7eb)', color: 'var(--success-color, #10b981)' }}>
                        {log.new_value ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default ChangeHistoryPanel;
