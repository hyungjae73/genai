import React, { useId, useState, useRef, useEffect, useCallback } from 'react';
import './Select.css';

export interface SelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  'aria-label'?: string;
  /** When true, renders a filterable combobox instead of a plain select */
  filterable?: boolean;
  /** Placeholder text for the filterable input */
  placeholder?: string;
}

export const Select: React.FC<SelectProps> = ({
  label,
  value,
  onChange,
  options,
  'aria-label': ariaLabel,
  filterable = false,
  placeholder,
}) => {
  const id = useId();

  if (!filterable) {
    return (
      <div className="select-field">
        <label className="select-field__label" htmlFor={id}>
          {label}
        </label>
        <select
          id={id}
          className="select-field__select"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={ariaLabel}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <FilterableSelect
      id={id}
      label={label}
      value={value}
      onChange={onChange}
      options={options}
      ariaLabel={ariaLabel}
      placeholder={placeholder}
    />
  );
};

/* ---- Filterable combobox sub-component ---- */

interface FilterableSelectInternalProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  ariaLabel?: string;
  placeholder?: string;
}

const FilterableSelect: React.FC<FilterableSelectInternalProps> = ({
  id,
  label,
  value,
  onChange,
  options,
  ariaLabel,
  placeholder,
}) => {
  const selectedLabel = options.find((o) => o.value === value)?.label ?? '';
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = `${id}-listbox`;

  const filtered = options.filter((o) =>
    o.label.toLowerCase().includes(query.toLowerCase()),
  );

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selectOption = useCallback(
    (optionValue: string) => {
      onChange(optionValue);
      setOpen(false);
      setQuery('');
      setHighlightIndex(-1);
    },
    [onChange],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightIndex((prev) => Math.min(prev + 1, filtered.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightIndex((prev) => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightIndex >= 0 && highlightIndex < filtered.length) {
          selectOption(filtered[highlightIndex].value);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        setQuery('');
        setHighlightIndex(-1);
        break;
    }
  };

  return (
    <div className="select-field select-field--filterable" ref={containerRef}>
      <label className="select-field__label" htmlFor={id}>
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        className="select-field__select"
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-label={ariaLabel}
        aria-autocomplete="list"
        aria-activedescendant={
          highlightIndex >= 0 ? `${id}-option-${highlightIndex}` : undefined
        }
        value={open ? query : selectedLabel}
        placeholder={placeholder ?? '入力して絞り込み...'}
        onChange={(e) => {
          setQuery(e.target.value);
          if (!open) setOpen(true);
          setHighlightIndex(-1);
        }}
        onFocus={() => {
          setOpen(true);
          setQuery('');
        }}
        onKeyDown={handleKeyDown}
        autoComplete="off"
      />
      {open && (
        <ul
          id={listboxId}
          className="select-field__listbox"
          role="listbox"
          aria-label={ariaLabel}
        >
          {filtered.length === 0 ? (
            <li className="select-field__option select-field__option--empty">
              該当なし
            </li>
          ) : (
            filtered.map((option, idx) => (
              <li
                key={option.value}
                id={`${id}-option-${idx}`}
                className={`select-field__option${
                  option.value === value ? ' select-field__option--selected' : ''
                }${idx === highlightIndex ? ' select-field__option--highlighted' : ''}`}
                role="option"
                aria-selected={option.value === value}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(option.value);
                }}
                onMouseEnter={() => setHighlightIndex(idx)}
              >
                {option.label}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
};

export default Select;
