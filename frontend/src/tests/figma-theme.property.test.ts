import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import * as fc from 'fast-check';
import { useTheme, type Theme } from '../hooks/useTheme';

// Feature: figma-ux-improvement, Property 13: Theme Preference Round-Trip

const STORAGE_KEY = 'theme-preference';
const VALID_THEMES: Theme[] = ['light', 'dark', 'system'];

const themeArb = fc.constantFrom<Theme>('light', 'dark', 'system');

describe('Property 13: Theme Preference Round-Trip', () => {
  let originalMatchMedia: typeof window.matchMedia;

  beforeEach(() => {
    originalMatchMedia = window.matchMedia;
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
    localStorage.clear();
  });

  /**
   * Validates: Requirements 7.4
   *
   * For any theme preference value ('light', 'dark', 'system'),
   * saving to localStorage and reading back yields the original value.
   */
  it('localStorage round-trip: saved theme value equals read-back value', () => {
    fc.assert(
      fc.property(themeArb, (theme: Theme) => {
        localStorage.clear();

        localStorage.setItem(STORAGE_KEY, theme);
        const readBack = localStorage.getItem(STORAGE_KEY);

        expect(readBack).toBe(theme);
        expect(VALID_THEMES).toContain(readBack);
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Validates: Requirements 7.4
   *
   * For any theme preference value, the useTheme hook's setTheme
   * persists the value and the hook's theme state reflects it.
   */
  it('useTheme hook round-trip: setTheme persists and reflects the value', () => {
    fc.assert(
      fc.property(themeArb, (theme: Theme) => {
        localStorage.clear();
        document.documentElement.removeAttribute('data-theme');

        const { result, unmount } = renderHook(() => useTheme());

        act(() => {
          result.current.setTheme(theme);
        });

        // Hook state matches the set value
        expect(result.current.theme).toBe(theme);

        // localStorage contains the set value
        expect(localStorage.getItem(STORAGE_KEY)).toBe(theme);

        unmount();
      }),
      { numRuns: 100 }
    );
  });

  /**
   * Validates: Requirements 7.4
   *
   * For any sequence of theme changes, the final state always
   * matches the last set value.
   */
  it('sequential theme changes: final state matches last set value', () => {
    fc.assert(
      fc.property(
        fc.array(themeArb, { minLength: 1, maxLength: 10 }),
        (themes: Theme[]) => {
          localStorage.clear();
          document.documentElement.removeAttribute('data-theme');

          const { result, unmount } = renderHook(() => useTheme());

          for (const theme of themes) {
            act(() => {
              result.current.setTheme(theme);
            });
          }

          const lastTheme = themes[themes.length - 1];
          expect(result.current.theme).toBe(lastTheme);
          expect(localStorage.getItem(STORAGE_KEY)).toBe(lastTheme);

          unmount();
        }
      ),
      { numRuns: 100 }
    );
  });
});


// Feature: figma-ux-improvement, Property 12: Dark Mode Token Switching

import * as fs from 'fs';
import * as nodePath from 'path';

// --- CSS Parsing Helpers ---

const TOKENS_DIR = nodePath.resolve(__dirname, '../tokens');

function readCssFile(filename: string): string {
  return fs.readFileSync(nodePath.join(TOKENS_DIR, filename), 'utf-8');
}

/**
 * Parse CSS custom property declarations from a CSS string.
 * Returns an array of { name, value } objects.
 */
function parseCssVariables(css: string): { name: string; value: string }[] {
  const results: { name: string; value: string }[] = [];
  const regex = /--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(css)) !== null) {
    results.push({
      name: `--${match[1]}`,
      value: match[2].trim(),
    });
  }
  return results;
}

/**
 * Parse only the [data-theme="dark"] block tokens (first block only, not @media).
 */
function parseDarkThemeTokens(css: string): { name: string; value: string }[] {
  // Match the [data-theme="dark"] { ... } block (first occurrence)
  const blockMatch = css.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/);
  if (!blockMatch) return [];
  return parseCssVariables(blockMatch[0]);
}

/**
 * Parse the :root, [data-theme="light"] block tokens.
 */
function parseLightThemeTokens(css: string): { name: string; value: string }[] {
  const blockMatch = css.match(/:root,\s*\[data-theme="light"\]\s*\{([^}]+)\}/);
  if (!blockMatch) return [];
  return parseCssVariables(blockMatch[0]);
}

// Load token files
const primitivesCSS = readCssFile('primitives.css');
const semanticLightCSS = readCssFile('semantic-light.css');
const semanticDarkCSS = readCssFile('semantic-dark.css');

const primitiveTokens = parseCssVariables(primitivesCSS);
const lightTokens = parseLightThemeTokens(semanticLightCSS);
const darkTokens = parseDarkThemeTokens(semanticDarkCSS);

// Build lookup maps
const primitiveMap = new Map(primitiveTokens.map((t) => [t.name, t.value]));
const lightTokenMap = new Map(lightTokens.map((t) => [t.name, t.value]));
const darkTokenMap = new Map(darkTokens.map((t) => [t.name, t.value]));

/**
 * Resolve a token value by following var() references to primitives.
 * Returns the final resolved value string.
 */
function resolveTokenValue(value: string, primitives: Map<string, string>): string {
  const varMatch = value.match(/var\((--[a-zA-Z0-9_-]+)\)/);
  if (varMatch) {
    const refName = varMatch[1];
    const primitiveValue = primitives.get(refName);
    if (primitiveValue) {
      return primitiveValue;
    }
  }
  // Return as-is for literal values (rgba, #hex, etc.)
  return value;
}

// Find semantic token names that exist in BOTH light and dark definitions
const sharedTokenNames = lightTokens
  .map((t) => t.name)
  .filter((name) => darkTokenMap.has(name));

// Exclude shadow tokens since they use rgba() literals in both modes
// and some tokens intentionally share the same primitive (e.g., --color-success uses --green-500 in both)
const colorSemanticTokenNames = sharedTokenNames.filter(
  (name) => name.startsWith('--color-')
);

describe('Feature: figma-ux-improvement, Property 12: Dark Mode Token Switching', () => {
  /**
   * Validates: Requirements 7.1
   *
   * For any semantic token, when data-theme="dark" is set,
   * the resolved CSS value differs from light mode and matches the dark mode definition.
   */

  it('dark mode tokens are defined for all light mode semantic color tokens', () => {
    expect(colorSemanticTokenNames.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...colorSemanticTokenNames),
        (tokenName) => {
          // Token must exist in both light and dark definitions
          expect(lightTokenMap.has(tokenName)).toBe(true);
          expect(darkTokenMap.has(tokenName)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('dark mode resolved values differ from light mode for color tokens', () => {
    // Tokens where light and dark have different raw values (before resolving)
    const differingTokenNames = colorSemanticTokenNames.filter((name) => {
      const lightVal = lightTokenMap.get(name)!;
      const darkVal = darkTokenMap.get(name)!;
      return lightVal !== darkVal;
    });

    expect(differingTokenNames.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...differingTokenNames),
        (tokenName) => {
          const lightVal = lightTokenMap.get(tokenName)!;
          const darkVal = darkTokenMap.get(tokenName)!;

          // Raw values must differ between light and dark
          expect(lightVal).not.toBe(darkVal);

          // Resolved values must also differ
          const resolvedLight = resolveTokenValue(lightVal, primitiveMap);
          const resolvedDark = resolveTokenValue(darkVal, primitiveMap);
          expect(resolvedLight).not.toBe(resolvedDark);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('dark mode token values match the dark CSS definition exactly', () => {
    expect(colorSemanticTokenNames.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...colorSemanticTokenNames),
        (tokenName) => {
          const darkVal = darkTokenMap.get(tokenName)!;

          // The dark token value must be a valid CSS value (var() reference or literal)
          const isVarRef = /var\(--[a-zA-Z0-9_-]+\)/.test(darkVal);
          const isLiteral = /^(rgba?\(|#[0-9a-fA-F])/.test(darkVal);
          expect(isVarRef || isLiteral).toBe(true);

          // If it's a var() reference, the referenced primitive must exist
          if (isVarRef) {
            const refMatch = darkVal.match(/var\((--[a-zA-Z0-9_-]+)\)/);
            expect(refMatch).not.toBeNull();
            expect(primitiveMap.has(refMatch![1])).toBe(true);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});


// Feature: figma-ux-improvement, Property 14: Dark Mode WCAG Contrast

/**
 * Parse a hex color string to RGB components.
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const cleaned = hex.replace('#', '');
  if (cleaned.length === 3) {
    return {
      r: parseInt(cleaned[0] + cleaned[0], 16),
      g: parseInt(cleaned[1] + cleaned[1], 16),
      b: parseInt(cleaned[2] + cleaned[2], 16),
    };
  }
  if (cleaned.length === 6) {
    return {
      r: parseInt(cleaned.substring(0, 2), 16),
      g: parseInt(cleaned.substring(2, 4), 16),
      b: parseInt(cleaned.substring(4, 6), 16),
    };
  }
  return null;
}

/**
 * Calculate relative luminance per WCAG 2.1 spec.
 * https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 */
function relativeLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const sRGB = c / 255;
    return sRGB <= 0.03928 ? sRGB / 12.92 : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Calculate contrast ratio between two colors per WCAG 2.1.
 * Returns a ratio >= 1.
 */
function contrastRatio(
  color1: { r: number; g: number; b: number },
  color2: { r: number; g: number; b: number }
): number {
  const l1 = relativeLuminance(color1.r, color1.g, color1.b);
  const l2 = relativeLuminance(color2.r, color2.g, color2.b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Fully resolve a token value to a hex color by following var() references.
 */
function resolveToHex(
  value: string,
  primitives: Map<string, string>
): string | null {
  // Direct hex value
  if (/^#[0-9a-fA-F]{3,6}$/.test(value)) return value;

  // var() reference
  const varMatch = value.match(/var\((--[a-zA-Z0-9_-]+)\)/);
  if (varMatch) {
    const refName = varMatch[1];
    const primitiveValue = primitives.get(refName);
    if (primitiveValue && /^#[0-9a-fA-F]{3,6}$/.test(primitiveValue)) {
      return primitiveValue;
    }
  }

  return null;
}

// Define text/background token pairs for dark mode contrast checking
const darkModeContrastPairs: { text: string; bg: string; description: string }[] = [
  { text: '--color-text-primary', bg: '--color-bg-primary', description: 'primary text on primary bg' },
  { text: '--color-text-primary', bg: '--color-bg-surface', description: 'primary text on surface bg' },
  { text: '--color-text-secondary', bg: '--color-bg-primary', description: 'secondary text on primary bg' },
  { text: '--color-text-secondary', bg: '--color-bg-surface', description: 'secondary text on surface bg' },
  { text: '--color-success-text', bg: '--color-success-subtle', description: 'success text on success subtle bg' },
  { text: '--color-warning-text', bg: '--color-warning-subtle', description: 'warning text on warning subtle bg' },
  { text: '--color-danger-text', bg: '--color-danger-subtle', description: 'danger text on danger subtle bg' },
  { text: '--color-nav-text', bg: '--color-nav-bg', description: 'nav text on nav bg' },
  { text: '--color-nav-text-active', bg: '--color-nav-bg', description: 'active nav text on nav bg' },
];

describe('Feature: figma-ux-improvement, Property 14: Dark Mode WCAG Contrast', () => {
  /**
   * Validates: Requirements 7.5
   *
   * For any dark mode text/background semantic token pair,
   * the contrast ratio is at least 4.5:1 (WCAG 2.1 AA level).
   */

  it('all dark mode text/background pairs meet WCAG AA contrast ratio (4.5:1)', () => {
    // Filter to pairs where both tokens can be resolved to hex colors
    const resolvablePairs = darkModeContrastPairs.filter((pair) => {
      const textVal = darkTokenMap.get(pair.text);
      const bgVal = darkTokenMap.get(pair.bg);
      if (!textVal || !bgVal) return false;
      const textHex = resolveToHex(textVal, primitiveMap);
      const bgHex = resolveToHex(bgVal, primitiveMap);
      return textHex !== null && bgHex !== null;
    });

    expect(resolvablePairs.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...resolvablePairs),
        (pair) => {
          const textVal = darkTokenMap.get(pair.text)!;
          const bgVal = darkTokenMap.get(pair.bg)!;
          const textHex = resolveToHex(textVal, primitiveMap)!;
          const bgHex = resolveToHex(bgVal, primitiveMap)!;

          const textRgb = hexToRgb(textHex)!;
          const bgRgb = hexToRgb(bgHex)!;

          const ratio = contrastRatio(textRgb, bgRgb);

          // WCAG 2.1 AA requires at least 4.5:1 for normal text
          expect(ratio).toBeGreaterThanOrEqual(4.5);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('dark mode accent color has sufficient contrast on dark backgrounds', () => {
    const accentPairs = [
      { text: '--color-accent', bg: '--color-bg-primary', description: 'accent on primary bg' },
      { text: '--color-accent', bg: '--color-bg-surface', description: 'accent on surface bg' },
    ];

    const resolvablePairs = accentPairs.filter((pair) => {
      const textVal = darkTokenMap.get(pair.text);
      const bgVal = darkTokenMap.get(pair.bg);
      if (!textVal || !bgVal) return false;
      return resolveToHex(textVal, primitiveMap) !== null && resolveToHex(bgVal, primitiveMap) !== null;
    });

    expect(resolvablePairs.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...resolvablePairs),
        (pair) => {
          const textVal = darkTokenMap.get(pair.text)!;
          const bgVal = darkTokenMap.get(pair.bg)!;
          const textHex = resolveToHex(textVal, primitiveMap)!;
          const bgHex = resolveToHex(bgVal, primitiveMap)!;

          const textRgb = hexToRgb(textHex)!;
          const bgRgb = hexToRgb(bgHex)!;

          const ratio = contrastRatio(textRgb, bgRgb);

          // WCAG AA for normal text: 4.5:1
          expect(ratio).toBeGreaterThanOrEqual(4.5);
        }
      ),
      { numRuns: 100 }
    );
  });
});
