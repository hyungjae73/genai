import React from 'react';
import type { FieldSchema } from '../../services/api';
import './DynamicFieldInput.css';

export interface DynamicFieldInputProps {
  schema: FieldSchema;
  value: unknown;
  onChange: (fieldName: string, value: unknown) => void;
  error?: string;
}

interface CurrencyValue {
  amount: number | string;
  currency: string;
}

function isCurrencyValue(v: unknown): v is CurrencyValue {
  return typeof v === 'object' && v !== null && 'amount' in v && 'currency' in v;
}

const DynamicFieldInput: React.FC<DynamicFieldInputProps> = ({ schema, value, onChange, error }) => {
  const { field_name, field_type, is_required } = schema;
  const inputClass = `dynamic-field__input${error ? ' dynamic-field__input--error' : ''}`;

  const renderInput = () => {
    switch (field_type) {
      case 'text':
        return (
          <input
            type="text"
            id={field_name}
            className={inputClass}
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(field_name, e.target.value)}
          />
        );

      case 'number':
        return (
          <input
            type="number"
            id={field_name}
            className={inputClass}
            value={value !== undefined && value !== null ? String(value) : ''}
            onChange={(e) => onChange(field_name, e.target.value === '' ? '' : Number(e.target.value))}
          />
        );

      case 'currency': {
        const currVal = isCurrencyValue(value) ? value : { amount: '', currency: '' };
        return (
          <div className="dynamic-field__currency">
            <input
              type="number"
              id={`${field_name}_amount`}
              className={`dynamic-field__input dynamic-field__currency-amount${error ? ' dynamic-field__input--error' : ''}`}
              placeholder="金額"
              value={currVal.amount !== undefined ? String(currVal.amount) : ''}
              onChange={(e) =>
                onChange(field_name, {
                  ...currVal,
                  amount: e.target.value === '' ? '' : Number(e.target.value),
                })
              }
            />
            <input
              type="text"
              id={`${field_name}_currency`}
              className={`dynamic-field__input dynamic-field__currency-code${error ? ' dynamic-field__input--error' : ''}`}
              placeholder="通貨 (例: JPY)"
              value={currVal.currency}
              onChange={(e) => onChange(field_name, { ...currVal, currency: e.target.value })}
            />
          </div>
        );
      }

      case 'percentage':
        return (
          <div className="dynamic-field__percentage">
            <input
              type="number"
              id={field_name}
              className={inputClass}
              min={0}
              max={100}
              value={value !== undefined && value !== null ? String(value) : ''}
              onChange={(e) => onChange(field_name, e.target.value === '' ? '' : Number(e.target.value))}
            />
            <span className="dynamic-field__percentage-symbol">%</span>
          </div>
        );

      case 'date':
        return (
          <input
            type="date"
            id={field_name}
            className={inputClass}
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(field_name, e.target.value)}
          />
        );

      case 'boolean':
        return (
          <div className="dynamic-field__checkbox-row">
            <input
              type="checkbox"
              id={field_name}
              className="dynamic-field__checkbox"
              checked={Boolean(value)}
              onChange={(e) => onChange(field_name, e.target.checked)}
            />
            <label htmlFor={field_name}>{field_name}</label>
          </div>
        );

      case 'list':
        return (
          <>
            <textarea
              id={field_name}
              className={`dynamic-field__textarea${error ? ' dynamic-field__textarea--error' : ''}`}
              value={typeof value === 'string' ? value : Array.isArray(value) ? (value as string[]).join(', ') : ''}
              onChange={(e) => onChange(field_name, e.target.value)}
            />
            <span className="dynamic-field__hint">カンマ区切りで複数の値を入力できます</span>
          </>
        );

      default:
        return (
          <input
            type="text"
            id={field_name}
            className={inputClass}
            value={typeof value === 'string' ? value : ''}
            onChange={(e) => onChange(field_name, e.target.value)}
          />
        );
    }
  };

  return (
    <div className="dynamic-field">
      {field_type !== 'boolean' && (
        <label className="dynamic-field__label" htmlFor={field_name}>
          {field_name}
          {is_required && <span className="dynamic-field__required">*</span>}
        </label>
      )}
      {renderInput()}
      {error && <span className="dynamic-field__error">{error}</span>}
    </div>
  );
};

export default DynamicFieldInput;
