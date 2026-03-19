import React, { useState, useRef, useEffect } from 'react';

/* ------------------------------------------------------------------ */
/*  EditableField – inline editing with validation & save              */
/* ------------------------------------------------------------------ */

export type FieldType = 'text' | 'number' | 'currency';

export interface EditableFieldProps {
  /** Current display value */
  value: string;
  /** Field type for input validation */
  fieldType?: FieldType;
  /** Whether this field was manually corrected */
  isManuallyEdited?: boolean;
  /** Callback when user saves a new value */
  onSave: (newValue: string) => Promise<void>;
  /** Optional placeholder for empty values */
  placeholder?: string;
}

const EditableField: React.FC<EditableFieldProps> = ({
  value,
  fieldType = 'text',
  isManuallyEdited = false,
  onSave,
  placeholder = '値を入力',
}) => {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  // Sync external value changes
  useEffect(() => {
    if (!editing) setEditValue(value);
  }, [value, editing]);

  const validate = (val: string): string | null => {
    if (fieldType === 'number' || fieldType === 'currency') {
      if (val.trim() === '') return null; // allow empty
      const num = Number(val.replace(/,/g, ''));
      if (isNaN(num)) return '数値を入力してください';
      if (fieldType === 'currency' && num < 0) return '0以上の値を入力してください';
    }
    return null;
  };

  const handleStartEdit = () => {
    setEditing(true);
    setEditValue(value);
    setError(null);
  };

  const handleCancel = () => {
    setEditing(false);
    setEditValue(value);
    setError(null);
  };

  const handleSave = async () => {
    const validationError = validate(editValue);
    if (validationError) {
      setError(validationError);
      return;
    }

    try {
      setSaving(true);
      setError(null);
      await onSave(editValue);
      setEditing(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '保存に失敗しました';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  if (editing) {
    return (
      <span className="editable-field editable-field--editing" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
        <input
          ref={inputRef}
          type={fieldType === 'number' || fieldType === 'currency' ? 'text' : 'text'}
          inputMode={fieldType === 'number' || fieldType === 'currency' ? 'decimal' : 'text'}
          value={editValue}
          onChange={(e) => {
            setEditValue(e.target.value);
            setError(null);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={saving}
          aria-label="フィールド編集"
          style={{
            padding: '0.2rem 0.4rem',
            fontSize: '0.875rem',
            border: error ? '1px solid var(--danger-color, #ef4444)' : '1px solid var(--border-color, #e5e7eb)',
            borderRadius: '4px',
            minWidth: '80px',
            maxWidth: '200px',
          }}
        />
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="btn btn-sm"
          aria-label="保存"
          style={{
            padding: '0.15rem 0.4rem',
            fontSize: '0.75rem',
            backgroundColor: 'var(--success-color, #10b981)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: saving ? 'wait' : 'pointer',
          }}
        >
          {saving ? '...' : '✓'}
        </button>
        <button
          type="button"
          onClick={handleCancel}
          disabled={saving}
          className="btn btn-sm"
          aria-label="キャンセル"
          style={{
            padding: '0.15rem 0.4rem',
            fontSize: '0.75rem',
            backgroundColor: 'var(--text-secondary, #6b7280)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
        {error && (
          <span style={{ color: 'var(--danger-color, #ef4444)', fontSize: '0.7rem' }}>
            {error}
          </span>
        )}
      </span>
    );
  }

  return (
    <span className="editable-field" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
      <span style={{ position: 'relative' }}>
        {value || <span style={{ color: 'var(--text-secondary, #6b7280)' }}>—</span>}
        {isManuallyEdited && (
          <span
            className="editable-field__manual-indicator"
            title="手動修正済み"
            style={{
              display: 'inline-block',
              marginLeft: '0.25rem',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: 'var(--primary-color, #2563eb)',
              verticalAlign: 'middle',
            }}
          />
        )}
      </span>
      <button
        type="button"
        onClick={handleStartEdit}
        className="btn btn-sm"
        aria-label={`${value} を編集`}
        style={{
          padding: '0.1rem 0.3rem',
          fontSize: '0.7rem',
          backgroundColor: 'transparent',
          border: '1px solid var(--border-color, #e5e7eb)',
          borderRadius: '4px',
          cursor: 'pointer',
          color: 'var(--text-secondary, #6b7280)',
        }}
      >
        ✎
      </button>
    </span>
  );
};

export default EditableField;
