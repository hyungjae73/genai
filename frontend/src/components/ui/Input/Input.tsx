import React, { useId } from 'react';
import './Input.css';

export interface InputProps {
  label: string;
  type?: 'text' | 'url' | 'email' | 'search';
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
  'aria-describedby'?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  type = 'text',
  value,
  onChange,
  error,
  placeholder,
  'aria-describedby': ariaDescribedBy,
}) => {
  const id = useId();
  const errorId = `${id}-error`;

  const describedBy = [
    error ? errorId : undefined,
    ariaDescribedBy,
  ]
    .filter(Boolean)
    .join(' ') || undefined;

  const inputClasses = [
    'input-field__input',
    error ? 'input-field__input--error' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="input-field">
      <label className="input-field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className={inputClasses}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-describedby={describedBy}
        aria-invalid={error ? true : undefined}
      />
      {error && (
        <span id={errorId} className="input-field__error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
};

export default Input;
