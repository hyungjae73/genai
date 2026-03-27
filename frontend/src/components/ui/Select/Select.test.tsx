import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Select } from './Select';

const options = [
  { value: 'a', label: 'Option A' },
  { value: 'b', label: 'Option B' },
  { value: 'c', label: 'Option C' },
];

describe('Select', () => {
  it('renders label and select', () => {
    render(<Select label="Category" value="a" onChange={() => {}} options={options} />);
    expect(screen.getByLabelText('Category')).toBeInTheDocument();
  });

  it('renders all options', () => {
    render(<Select label="Category" value="a" onChange={() => {}} options={options} />);
    expect(screen.getAllByRole('option')).toHaveLength(3);
  });

  it('selects the correct value', () => {
    render(<Select label="Category" value="b" onChange={() => {}} options={options} />);
    expect(screen.getByLabelText('Category')).toHaveValue('b');
  });

  it('calls onChange with selected value', () => {
    const handleChange = vi.fn();
    render(<Select label="Category" value="a" onChange={handleChange} options={options} />);
    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'c' } });
    expect(handleChange).toHaveBeenCalledWith('c');
  });

  it('supports aria-label', () => {
    render(
      <Select label="Category" value="a" onChange={() => {}} options={options} aria-label="Pick category" />
    );
    expect(screen.getByLabelText('Category')).toHaveAttribute('aria-label', 'Pick category');
  });

  it('renders option labels correctly', () => {
    render(<Select label="Category" value="a" onChange={() => {}} options={options} />);
    expect(screen.getByText('Option A')).toBeInTheDocument();
    expect(screen.getByText('Option B')).toBeInTheDocument();
    expect(screen.getByText('Option C')).toBeInTheDocument();
  });

  it('renders with empty options', () => {
    render(<Select label="Empty" value="" onChange={() => {}} options={[]} />);
    expect(screen.getByLabelText('Empty')).toBeInTheDocument();
    expect(screen.queryAllByRole('option')).toHaveLength(0);
  });
});
