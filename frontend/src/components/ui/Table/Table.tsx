import React from 'react';
import './Table.css';

export interface TableColumn<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
}

export interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  mobileLayout?: 'card' | 'scroll';
  emptyMessage?: string;
  'aria-label': string;
}

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  mobileLayout = 'card',
  emptyMessage = 'No data',
  'aria-label': ariaLabel,
}: TableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="table-empty" role="status">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={`table-wrapper table-wrapper--mobile-${mobileLayout}`}>
      {/* Desktop / scroll-mode table */}
      <table className="table" aria-label={ariaLabel}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIdx) => (
            <tr key={rowIdx}>
              {columns.map((col) => (
                <td key={col.key} data-label={col.header}>
                  {col.render
                    ? col.render(row)
                    : (row[col.key] as React.ReactNode) ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Card-mode mobile view */}
      <div className="table-cards" role="list" aria-label={ariaLabel}>
        {data.map((row, rowIdx) => (
          <div className="table-card" role="listitem" key={rowIdx}>
            {columns.map((col) => (
              <div className="table-card__field" key={col.key}>
                <span className="table-card__label">{col.header}</span>
                <span className="table-card__value">
                  {col.render
                    ? col.render(row)
                    : (row[col.key] as React.ReactNode) ?? ''}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Table;
