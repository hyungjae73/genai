import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Input } from './Input';

describe('Input', () => {
  it('renders label and input', () => {
    render(<Input label="Name" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
  });

  it('renders with correct type', () => {
    render(<Input label="Email" type="email" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Email')).toHaveAttribute('type', 'email');
  });

  it('calls onChange with new value', () => {
    const handleChange = vi.fn();
    render(<Input label="URL" value="" onChange={handleChange} />);
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://example.com' } });
    expect(handleChange).toHaveBeenCalledWith('https://example.com');
  });

  it('renders placeholder', () => {
    render(<Input label="Search" placeholder="Type here..." value="" onChange={() => {}} />);
    expect(screen.getByPlaceholderText('Type here...')).toBeInTheDocument();
  });

  it('renders error message with role=alert', () => {
    render(<Input label="URL" value="" onChange={() => {}} error="Invalid URL" />);
    expect(screen.getByRole('alert')).toHaveTextContent('Invalid URL');
  });

  it('sets aria-invalid when error is present', () => {
    render(<Input label="URL" value="" onChange={() => {}} error="Required" />);
    expect(screen.getByLabelText('URL')).toHaveAttribute('aria-invalid', 'true');
  });

  it('links error to input via aria-describedby', () => {
    render(<Input label="URL" value="" onChange={() => {}} error="Bad" />);
    const input = screen.getByLabelText('URL');
    const describedBy = input.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    const errorEl = document.getElementById(describedBy!);
    expect(errorEl).toHaveTextContent('Bad');
  });

  it('supports custom aria-describedby', () => {
    render(<Input label="URL" value="" onChange={() => {}} aria-describedby="help-text" />);
    expect(screen.getByLabelText('URL')).toHaveAttribute('aria-describedby', 'help-text');
  });

  it('merges custom aria-describedby with error id', () => {
    render(<Input label="URL" value="" onChange={() => {}} error="Err" aria-describedby="help" />);
    const describedBy = screen.getByLabelText('URL').getAttribute('aria-describedby');
    expect(describedBy).toContain('help');
  });

  it('defaults type to text', () => {
    render(<Input label="Name" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Name')).toHaveAttribute('type', 'text');
  });
});
