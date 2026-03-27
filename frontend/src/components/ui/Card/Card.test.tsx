import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Card } from './Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Hello</Card>);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('applies default padding class (md)', () => {
    const { container } = render(<Card>Content</Card>);
    expect(container.firstChild).toHaveClass('card--pad-md');
  });

  it('applies all three padding sizes', () => {
    const sizes = ['sm', 'md', 'lg'] as const;
    for (const s of sizes) {
      const { container, unmount } = render(<Card padding={s}>P</Card>);
      expect(container.firstChild).toHaveClass(`card--pad-${s}`);
      unmount();
    }
  });

  it('applies borderLeft variant classes', () => {
    const variants = ['success', 'warning', 'danger', 'info'] as const;
    for (const v of variants) {
      const { container, unmount } = render(<Card borderLeft={v}>B</Card>);
      expect(container.firstChild).toHaveClass(`card--border-${v}`);
      unmount();
    }
  });

  it('does not apply borderLeft class when not provided', () => {
    const { container } = render(<Card>No border</Card>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).not.toMatch(/card--border/);
  });

  it('applies hoverable class when hoverable is true', () => {
    const { container } = render(<Card hoverable>Hover me</Card>);
    expect(container.firstChild).toHaveClass('card--hoverable');
  });

  it('does not apply hoverable class by default', () => {
    const { container } = render(<Card>Static</Card>);
    const el = container.firstChild as HTMLElement;
    expect(el.className).not.toContain('card--hoverable');
  });

  it('merges custom className', () => {
    const { container } = render(<Card className="my-custom">Custom</Card>);
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveClass('card');
    expect(el).toHaveClass('my-custom');
  });

  it('renders as a div element', () => {
    const { container } = render(<Card>Div</Card>);
    expect(container.firstChild?.nodeName).toBe('DIV');
  });

  it('combines all props correctly', () => {
    const { container } = render(
      <Card padding="lg" borderLeft="danger" hoverable className="extra">
        All props
      </Card>
    );
    const el = container.firstChild as HTMLElement;
    expect(el).toHaveClass('card');
    expect(el).toHaveClass('card--pad-lg');
    expect(el).toHaveClass('card--border-danger');
    expect(el).toHaveClass('card--hoverable');
    expect(el).toHaveClass('extra');
  });
});
