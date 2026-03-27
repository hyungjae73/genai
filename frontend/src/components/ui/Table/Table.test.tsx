import { render, screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Table } from './Table';
import type { TableColumn } from './Table';

interface TestRow {
  id: number;
  name: string;
  status: string;
  [key: string]: unknown;
}

const columns: TableColumn<TestRow>[] = [
  { key: 'id', header: 'ID' },
  { key: 'name', header: 'Name' },
  { key: 'status', header: 'Status' },
];

const data: TestRow[] = [
  { id: 1, name: 'Alice', status: 'active' },
  { id: 2, name: 'Bob', status: 'inactive' },
];

describe('Table', () => {
  it('renders a table with aria-label', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    expect(screen.getByRole('table', { name: 'Users' })).toBeInTheDocument();
  });

  it('renders column headers', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    expect(screen.getByRole('columnheader', { name: 'ID' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument();
  });

  it('renders data rows', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    const rows = screen.getAllByRole('row');
    // 1 header row + 2 data rows
    expect(rows).toHaveLength(3);
  });

  it('renders cell values from data keys', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    expect(screen.getByRole('table')).toHaveTextContent('Alice');
    expect(screen.getByRole('table')).toHaveTextContent('Bob');
  });

  it('uses custom render function when provided', () => {
    const cols: TableColumn<TestRow>[] = [
      { key: 'name', header: 'Name', render: (row) => <strong>{row.name}</strong> },
    ];
    render(<Table columns={cols} data={data} aria-label="Users" />);
    const strongs = screen.getByRole('table').querySelectorAll('strong');
    expect(strongs).toHaveLength(2);
    expect(strongs[0]).toHaveTextContent('Alice');
  });

  it('shows empty message when data is empty', () => {
    render(<Table columns={columns} data={[]} aria-label="Users" emptyMessage="Nothing here" />);
    expect(screen.getByRole('status')).toHaveTextContent('Nothing here');
  });

  it('shows default empty message when none provided', () => {
    render(<Table columns={columns} data={[]} aria-label="Users" />);
    expect(screen.getByRole('status')).toHaveTextContent('No data');
  });

  it('applies mobile-card wrapper class by default', () => {
    const { container } = render(<Table columns={columns} data={data} aria-label="Users" />);
    expect(container.querySelector('.table-wrapper--mobile-card')).toBeInTheDocument();
  });

  it('applies mobile-scroll wrapper class when mobileLayout is scroll', () => {
    const { container } = render(
      <Table columns={columns} data={data} aria-label="Users" mobileLayout="scroll" />
    );
    expect(container.querySelector('.table-wrapper--mobile-scroll')).toBeInTheDocument();
  });

  it('renders card-mode mobile view with role=list', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    expect(screen.getByRole('list', { name: 'Users' })).toBeInTheDocument();
  });

  it('renders card items with header:value pairs', () => {
    render(<Table columns={columns} data={data} aria-label="Users" />);
    const listItems = screen.getAllByRole('listitem');
    expect(listItems).toHaveLength(2);
    // First card should contain all column headers as labels
    const firstCard = listItems[0];
    expect(within(firstCard).getByText('ID')).toBeInTheDocument();
    expect(within(firstCard).getByText('Name')).toBeInTheDocument();
  });

  it('sets data-label attribute on td elements', () => {
    const { container } = render(<Table columns={columns} data={data} aria-label="Users" />);
    const tds = container.querySelectorAll('td[data-label]');
    expect(tds.length).toBeGreaterThan(0);
    expect(tds[0]).toHaveAttribute('data-label', 'ID');
  });
});
