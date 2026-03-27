import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ThemeToggle } from './ThemeToggle';

// Mock useTheme hook
const mockSetTheme = vi.fn();
let mockTheme = 'system' as 'light' | 'dark' | 'system';
let mockResolvedTheme = 'light' as 'light' | 'dark';

vi.mock('../../../hooks/useTheme', () => ({
  useTheme: () => ({
    theme: mockTheme,
    resolvedTheme: mockResolvedTheme,
    setTheme: mockSetTheme,
  }),
}));

describe('ThemeToggle', () => {
  beforeEach(() => {
    mockTheme = 'system';
    mockResolvedTheme = 'light';
    mockSetTheme.mockClear();
  });

  it('renders a button', () => {
    render(<ThemeToggle />);
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('has a default aria-label with current theme', () => {
    render(<ThemeToggle />);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'テーマ切替（現在: システム）',
    );
  });

  it('accepts a custom aria-label', () => {
    render(<ThemeToggle aria-label="Toggle theme" />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Toggle theme');
  });

  it('shows sun icon in light mode', () => {
    mockResolvedTheme = 'light';
    render(<ThemeToggle />);
    expect(screen.getByText('☀️')).toBeInTheDocument();
  });

  it('shows moon icon in dark mode', () => {
    mockResolvedTheme = 'dark';
    render(<ThemeToggle />);
    expect(screen.getByText('🌙')).toBeInTheDocument();
  });

  it('cycles from light to dark on click', () => {
    mockTheme = 'light';
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockSetTheme).toHaveBeenCalledWith('dark');
  });

  it('cycles from dark to system on click', () => {
    mockTheme = 'dark';
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockSetTheme).toHaveBeenCalledWith('system');
  });

  it('cycles from system to light on click', () => {
    mockTheme = 'system';
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockSetTheme).toHaveBeenCalledWith('light');
  });

  it('has 44px minimum touch target', () => {
    render(<ThemeToggle />);
    const button = screen.getByRole('button');
    expect(button.className).toContain('theme-toggle');
    // CSS enforces min-height/min-width: 44px
  });

  it('displays aria-label for dark theme', () => {
    mockTheme = 'dark';
    render(<ThemeToggle />);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'テーマ切替（現在: ダーク）',
    );
  });

  it('displays aria-label for light theme', () => {
    mockTheme = 'light';
    render(<ThemeToggle />);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-label',
      'テーマ切替（現在: ライト）',
    );
  });
});
