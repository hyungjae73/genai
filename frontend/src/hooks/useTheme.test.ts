import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useTheme } from './useTheme';

describe('useTheme', () => {
  let originalMatchMedia: typeof window.matchMedia;
  let mediaListeners: Array<(e: MediaQueryListEvent) => void>;

  const mockMatchMedia = (matches: boolean) => {
    mediaListeners = [];
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      addEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
        mediaListeners.push(listener);
      },
      removeEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
        mediaListeners = mediaListeners.filter((l) => l !== listener);
      },
      dispatchEvent: vi.fn(),
    }));
  };

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    mockMatchMedia(false); // default: light system preference
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('defaults to system theme when no stored preference', () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('light');
  });

  it('reads stored theme from localStorage', () => {
    localStorage.setItem('theme-preference', 'dark');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
    expect(result.current.resolvedTheme).toBe('dark');
  });

  it('sets data-theme attribute on document element', () => {
    renderHook(() => useTheme());
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('setTheme updates theme, resolvedTheme, localStorage, and data-theme', () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme('dark');
    });

    expect(result.current.theme).toBe('dark');
    expect(result.current.resolvedTheme).toBe('dark');
    expect(localStorage.getItem('theme-preference')).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('resolves system theme using prefers-color-scheme', () => {
    mockMatchMedia(true); // dark system preference
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('dark');
  });

  it('updates resolved theme when system preference changes and theme is system', () => {
    let currentMatches = false;
    mediaListeners = [];
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      get matches() { return currentMatches; },
      media: query,
      addEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
        mediaListeners.push(listener);
      },
      removeEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
        mediaListeners = mediaListeners.filter((l) => l !== listener);
      },
      dispatchEvent: vi.fn(),
    }));

    const { result } = renderHook(() => useTheme());
    expect(result.current.resolvedTheme).toBe('light');

    // Simulate system preference change to dark
    currentMatches = true;
    act(() => {
      mediaListeners.forEach((listener) =>
        listener({ matches: true } as MediaQueryListEvent)
      );
    });

    expect(result.current.resolvedTheme).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('does not update resolved theme on system change when theme is explicit', () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme('dark');
    });

    // Simulate system preference change — should not affect explicit theme
    mockMatchMedia(false);
    act(() => {
      mediaListeners.forEach((listener) =>
        listener({ matches: false } as MediaQueryListEvent)
      );
    });

    expect(result.current.resolvedTheme).toBe('dark');
  });

  it('falls back to system when localStorage has invalid value', () => {
    localStorage.setItem('theme-preference', 'invalid-value');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('system');
  });

  it('handles localStorage access errors gracefully', () => {
    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Access denied');
    });

    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('light');

    getItemSpy.mockRestore();
  });

  it('handles localStorage write errors gracefully', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Access denied');
    });

    const { result } = renderHook(() => useTheme());

    // Should not throw
    act(() => {
      result.current.setTheme('dark');
    });

    expect(result.current.theme).toBe('dark');
    expect(result.current.resolvedTheme).toBe('dark');

    setItemSpy.mockRestore();
  });

  it('switching from explicit to system resolves based on system preference', () => {
    mockMatchMedia(true); // dark system preference
    localStorage.setItem('theme-preference', 'light');

    const { result } = renderHook(() => useTheme());
    expect(result.current.resolvedTheme).toBe('light');

    act(() => {
      result.current.setTheme('system');
    });

    expect(result.current.theme).toBe('system');
    expect(result.current.resolvedTheme).toBe('dark');
  });
});
