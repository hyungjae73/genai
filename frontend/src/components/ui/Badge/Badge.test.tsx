import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge variant="success">Active</Badge>);
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('applies variant and default size classes', () => {
    render(<Badge variant="danger">Error</Badge>);
    const badge = screen.getByRole('status');
    expect(badge.className).toContain('badge--danger');
    expect(badge.className).toContain('badge--md');
  });

  it('applies explicit size class', () => {
    render(<Badge variant="info" size="sm">Info</Badge>);
    const badge = screen.getByRole('status');
    expect(badge.className).toContain('badge--sm');
  });

  it('renders as a span element', () => {
    render(<Badge variant="neutral">Tag</Badge>);
    const badge = screen.getByRole('status');
    expect(badge.tagName).toBe('SPAN');
  });

  it('has role="status" for accessibility', () => {
    render(<Badge variant="warning">Pending</Badge>);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders all five variants without error', () => {
    const variants = ['success', 'warning', 'danger', 'info', 'neutral'] as const;
    for (const v of variants) {
      const { unmount } = render(<Badge variant={v}>{v}</Badge>);
      expect(screen.getByRole('status')).toHaveClass(`badge--${v}`);
      unmount();
    }
  });

  it('renders both sizes without error', () => {
    const sizes = ['sm', 'md'] as const;
    for (const s of sizes) {
      const { unmount } = render(<Badge variant="success" size={s}>{s}</Badge>);
      expect(screen.getByRole('status')).toHaveClass(`badge--${s}`);
      unmount();
    }
  });

  it('defaults size to md when not specified', () => {
    render(<Badge variant="success">Default</Badge>);
    expect(screen.getByRole('status')).toHaveClass('badge--md');
  });
});
