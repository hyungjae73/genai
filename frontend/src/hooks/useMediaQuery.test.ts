import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { classifyBreakpoint, useMediaQuery, useBreakpoint } from './useMediaQuery';

describe('classifyBreakpoint', () => {
  it('returns mobile for width < 768', () => {
    expect(classifyBreakpoint(0)).toBe('mobile');
    expect(classifyBreakpoint(320)).toBe('mobile');
    expect(classifyBreakpoint(767)).toBe('mobile');
  });

  it('returns tablet for width 768-1023', () => {
    expect(classifyBreakpoint(768)).toBe('tablet');
    expect(classifyBreakpoint(900)).toBe('tablet');
    expect(classifyBreakpoint(1023)).toBe('tablet');
  });

  it('returns desktop for width >= 1024', () => {
    expect(classifyBreakpoint(1024)).toBe('desktop');
    expect(classifyBreakpoint(1920)).toBe('desktop');
  });

  it('returns mobile for width 1', () => {
    expect(classifyBreakpoint(1)).toBe('mobile');
  });
});

describe('useMediaQuery', () => {
  let originalMatchMedia: typeof window.matchMedia;
  let listeners: Map<string, Array<(e: MediaQueryListEvent) => void>>;

  const mockMatchMedia = (matchFn: (query: string) => boolean) => {
    listeners = new Map();
    window.matchMedia = vi.fn().mockImplementation((query: string) => {
      if (!listeners.has(query)) listeners.set(query, []);
      return {
        get matches() { return matchFn(query); },
        media: query,
        addEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
          listeners.get(query)!.push(listener);
        },
        removeEventListener: (_event: string, listener: (e: MediaQueryListEvent) => void) => {
          const arr = listeners.get(query)!;
          listeners.set(query, arr.filter((l) => l !== listener));
        },
        dispatchEvent: vi.fn(),
      };
    });
  };

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('returns true when media query matches', () => {
    mockMatchMedia(() => true);
    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));
    expect(result.current).toBe(true);
  });

  it('returns false when media query does not match', () => {
    mockMatchMedia(() => false);
    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));
    expect(result.current).toBe(false);
  });

  it('updates when media query match changes', () => {
    let currentMatch = false;
    mockMatchMedia(() => currentMatch);

    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'));
    expect(result.current).toBe(false);

    currentMatch = true;
    act(() => {
      const queryListeners = listeners.get('(min-width: 1024px)') ?? [];
      queryListeners.forEach((l) => l({ matches: true } as MediaQueryListEvent));
    });

    expect(result.current).toBe(true);
  });

  it('cleans up listener on unmount', () => {
    mockMatchMedia(() => false);
    const { unmount } = renderHook(() => useMediaQuery('(min-width: 1024px)'));

    expect(listeners.get('(min-width: 1024px)')!.length).toBe(1);
    unmount();
    expect(listeners.get('(min-width: 1024px)')!.length).toBe(0);
  });
});

describe('useBreakpoint', () => {
  let originalMatchMedia: typeof window.matchMedia;

  const mockBreakpoint = (breakpoint: 'mobile' | 'tablet' | 'desktop') => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => {
      let matches = false;
      if (breakpoint === 'desktop' && query.includes('min-width: 1024px')) {
        matches = true;
      } else if (breakpoint === 'tablet' && query.includes('min-width: 768px') && query.includes('max-width: 1023px')) {
        matches = true;
      }
      return {
        matches,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      };
    });
  };

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it('returns desktop when viewport >= 1024px', () => {
    mockBreakpoint('desktop');
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('desktop');
  });

  it('returns tablet when viewport 768-1023px', () => {
    mockBreakpoint('tablet');
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('tablet');
  });

  it('returns mobile when viewport < 768px', () => {
    mockBreakpoint('mobile');
    const { result } = renderHook(() => useBreakpoint());
    expect(result.current).toBe('mobile');
  });
});
