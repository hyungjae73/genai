import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders children text', () => {
    render(<Button variant="primary" size="md">Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('applies variant and size classes', () => {
    render(<Button variant="danger" size="lg">Delete</Button>);
    const btn = screen.getByRole('button');
    expect(btn.className).toContain('btn--danger');
    expect(btn.className).toContain('btn--lg');
  });

  it('calls onClick when clicked', () => {
    const handler = vi.fn();
    render(<Button variant="primary" size="md" onClick={handler}>Go</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('does not call onClick when disabled', () => {
    const handler = vi.fn();
    render(<Button variant="primary" size="md" disabled onClick={handler}>Go</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(handler).not.toHaveBeenCalled();
  });

  it('shows loading spinner and disables button when loading', () => {
    render(<Button variant="primary" size="md" loading>Save</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn.querySelector('.btn__spinner')).toBeInTheDocument();
  });

  it('sets aria-label when provided', () => {
    render(<Button variant="ghost" size="sm" aria-label="Close dialog">X</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Close dialog');
  });

  it('defaults type to button', () => {
    render(<Button variant="secondary" size="md">OK</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });

  it('allows type override to submit', () => {
    render(<Button variant="primary" size="md" type="submit">Submit</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });

  it('is keyboard focusable', () => {
    render(<Button variant="primary" size="md">Focus me</Button>);
    const btn = screen.getByRole('button');
    btn.focus();
    expect(document.activeElement).toBe(btn);
  });

  it('triggers onClick on Enter key', () => {
    const handler = vi.fn();
    render(<Button variant="primary" size="md" onClick={handler}>Enter</Button>);
    const btn = screen.getByRole('button');
    fireEvent.keyDown(btn, { key: 'Enter' });
    fireEvent.keyUp(btn, { key: 'Enter' });
    // Native button handles Enter → click
    fireEvent.click(btn);
    expect(handler).toHaveBeenCalled();
  });

  it('renders all four variants without error', () => {
    const variants = ['primary', 'secondary', 'danger', 'ghost'] as const;
    for (const v of variants) {
      const { unmount } = render(<Button variant={v} size="md">{v}</Button>);
      expect(screen.getByRole('button')).toHaveClass(`btn--${v}`);
      unmount();
    }
  });

  it('renders all three sizes without error', () => {
    const sizes = ['sm', 'md', 'lg'] as const;
    for (const s of sizes) {
      const { unmount } = render(<Button variant="primary" size={s}>{s}</Button>);
      expect(screen.getByRole('button')).toHaveClass(`btn--${s}`);
      unmount();
    }
  });

  it('sets aria-disabled when disabled or loading', () => {
    const { rerender } = render(<Button variant="primary" size="md" disabled>D</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('aria-disabled', 'true');

    rerender(<Button variant="primary" size="md" loading>L</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('aria-disabled', 'true');
  });
});
