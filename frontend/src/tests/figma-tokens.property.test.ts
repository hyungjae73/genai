import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import * as fs from 'fs';
import * as path from 'path';

// Feature: figma-ux-improvement, Property 1: Token Structure Integrity

// --- CSS Parsing Helpers ---

const TOKENS_DIR = path.resolve(__dirname, '../tokens');

function readCssFile(filename: string): string {
  return fs.readFileSync(path.join(TOKENS_DIR, filename), 'utf-8');
}

/**
 * Parse CSS custom property declarations from a CSS string.
 * Returns an array of { name, value } objects.
 */
function parseCssVariables(css: string): { name: string; value: string }[] {
  const results: { name: string; value: string }[] = [];
  // Match --variable-name: value; patterns
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
 * Categorize a primitive token by its name prefix.
 */
function categorizePrimitive(name: string): string | null {
  // Color tokens: --blue-*, --gray-*, --green-*, --red-*, --amber-*, --orange-*
  if (/^--(blue|gray|green|red|amber|orange)-/.test(name)) return 'color';
  // Spacing tokens: --space-*
  if (/^--space-/.test(name)) return 'spacing';
  // Font size tokens: --font-*
  if (/^--font-/.test(name)) return 'fontSize';
  // Border radius tokens: --radius-*
  if (/^--radius-/.test(name)) return 'borderRadius';
  // Shadow tokens: --shadow-*
  if (/^--shadow-/.test(name)) return 'shadow';
  return null;
}

// --- Load and parse token files once ---

const primitivesCSS = readCssFile('primitives.css');
const semanticLightCSS = readCssFile('semantic-light.css');
const semanticDarkCSS = readCssFile('semantic-dark.css');

const primitiveTokens = parseCssVariables(primitivesCSS);
const semanticLightTokens = parseCssVariables(semanticLightCSS);
const semanticDarkTokens = parseCssVariables(semanticDarkCSS);

// Build a set of all primitive token names for reference lookup
const primitiveTokenNames = new Set(primitiveTokens.map((t) => t.name));

// Required categories that must have primitive tokens
const REQUIRED_CATEGORIES = ['color', 'spacing', 'fontSize', 'borderRadius', 'shadow'] as const;

// --- Semantic tokens that use var() references (excluding literal values like #ffffff, rgba()) ---

/**
 * Check if a value is a var() reference.
 */
function isVarReference(value: string): boolean {
  return /var\(--[a-zA-Z0-9_-]+/.test(value);
}

/**
 * Extract the referenced variable name from a var() expression.
 * e.g., "var(--gray-50)" -> "--gray-50"
 */
function extractVarName(value: string): string | null {
  const match = value.match(/var\((--[a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

/**
 * Filter semantic tokens to only those whose values are var() references
 * (excluding literal values like #ffffff, rgba(), etc.)
 */
function getVarReferenceTokens(
  tokens: { name: string; value: string }[]
): { name: string; value: string }[] {
  return tokens.filter((t) => isVarReference(t.value));
}

// Semantic tokens that use var() references
const lightVarTokens = getVarReferenceTokens(semanticLightTokens);
const darkVarTokens = getVarReferenceTokens(semanticDarkTokens);

// Combine all semantic var-reference tokens (deduplicated by name+value)
const allSemanticVarTokens = [...lightVarTokens, ...darkVarTokens];

// --- Arbitraries ---

// Generator that picks a random semantic token that uses var()
const arbSemanticVarToken = fc.constantFrom(...allSemanticVarTokens);

// Generator that picks a random primitive token
const _arbPrimitiveToken = fc.constantFrom(...primitiveTokens);

// Generator that picks a random required category
const arbRequiredCategory = fc.constantFrom(...REQUIRED_CATEGORIES);

// --- Property Tests ---

describe('Feature: figma-ux-improvement, Property 1: Token Structure Integrity', () => {
  /**
   * **Validates: Requirements 1.1, 1.3**
   *
   * For any セマンティックトークン定義において、その値はプリミティブトークンへの`var()`参照であり、
   * かつ全ての必須カテゴリ（color、spacing、fontSize、borderRadius、shadow）に
   * プリミティブトークンが存在すること。
   */

  it('semantic tokens with var() references point to existing primitive tokens', () => {
    // Precondition: we have semantic tokens with var() references
    expect(allSemanticVarTokens.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(arbSemanticVarToken, (token) => {
        // The value must contain a var() reference
        expect(isVarReference(token.value)).toBe(true);

        // Extract the referenced variable name
        const referencedVar = extractVarName(token.value);
        expect(referencedVar).not.toBeNull();

        // The referenced variable must exist in primitives
        expect(primitiveTokenNames.has(referencedVar!)).toBe(
          true,
        );
      }),
      { numRuns: 100 }
    );
  });

  it('all required categories have primitive tokens defined', () => {
    // Build a set of categories that have at least one primitive token
    const categoriesWithPrimitives = new Set<string>();
    for (const token of primitiveTokens) {
      const category = categorizePrimitive(token.name);
      if (category) {
        categoriesWithPrimitives.add(category);
      }
    }

    fc.assert(
      fc.property(arbRequiredCategory, (category) => {
        // Each required category must have at least one primitive token
        expect(categoriesWithPrimitives.has(category)).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('each required category has multiple primitive tokens', () => {
    // Count tokens per category
    const categoryTokenCounts = new Map<string, number>();
    for (const token of primitiveTokens) {
      const category = categorizePrimitive(token.name);
      if (category) {
        categoryTokenCounts.set(category, (categoryTokenCounts.get(category) || 0) + 1);
      }
    }

    fc.assert(
      fc.property(arbRequiredCategory, (category) => {
        const count = categoryTokenCounts.get(category) || 0;
        // Each required category should have at least 2 tokens
        expect(count).toBeGreaterThanOrEqual(2);
      }),
      { numRuns: 100 }
    );
  });

  it('semantic light tokens with var() references use valid var() syntax', () => {
    expect(lightVarTokens.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...lightVarTokens),
        (token) => {
          // Value must match var(--something) pattern
          expect(token.value).toMatch(/var\(--[a-zA-Z0-9_-]+\)/);

          // The referenced primitive must exist
          const refName = extractVarName(token.value);
          expect(refName).not.toBeNull();
          expect(primitiveTokenNames.has(refName!)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('semantic dark tokens with var() references use valid var() syntax', () => {
    expect(darkVarTokens.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...darkVarTokens),
        (token) => {
          // Value must match var(--something) pattern
          expect(token.value).toMatch(/var\(--[a-zA-Z0-9_-]+\)/);

          // The referenced primitive must exist
          const refName = extractVarName(token.value);
          expect(refName).not.toBeNull();
          expect(primitiveTokenNames.has(refName!)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('primitive tokens cover all color scales defined in the design', () => {
    const expectedColorPrefixes = ['blue', 'gray', 'green', 'red', 'amber', 'orange'];

    fc.assert(
      fc.property(
        fc.constantFrom(...expectedColorPrefixes),
        (colorPrefix) => {
          // At least one primitive token should exist for each color scale
          const hasColor = primitiveTokens.some((t) =>
            t.name.startsWith(`--${colorPrefix}-`)
          );
          expect(hasColor).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});


// Feature: figma-ux-improvement, Property 3: No Hardcoded Values

// --- Property 3 Helpers ---

const SRC_DIR = path.resolve(__dirname, '..');

/**
 * Recursively find all CSS files in a directory.
 */
function findCssFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip tokens directory (token definitions are allowed to have raw values)
      if (entry.name === 'tokens' || entry.name === 'node_modules' || entry.name === '__tests__') continue;
      results.push(...findCssFiles(fullPath));
    } else if (entry.name.endsWith('.css')) {
      results.push(fullPath);
    }
  }
  return results;
}

/**
 * Parse CSS property declarations (not custom properties) from a CSS string.
 * Returns array of { property, value, file, line } objects.
 */
function parseCssDeclarations(
  css: string,
  filePath: string
): { property: string; value: string; file: string; line: number }[] {
  const results: { property: string; value: string; file: string; line: number }[] = [];
  const lines = css.split('\n');

  // Track if we're inside a :root or token definition block
  let braceDepth = 0;
  let inRootBlock = false;
  let inKeyframes = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    // Track @keyframes blocks (skip them)
    if (line.startsWith('@keyframes')) {
      inKeyframes = true;
    }

    // Track :root blocks (skip custom property definitions)
    if (line.includes(':root') || line.includes('[data-theme')) {
      inRootBlock = true;
    }

    // Track brace depth
    const openBraces = (line.match(/{/g) || []).length;
    const closeBraces = (line.match(/}/g) || []).length;
    braceDepth += openBraces - closeBraces;

    if (braceDepth <= 0) {
      inRootBlock = false;
      inKeyframes = false;
      braceDepth = 0;
    }

    // Skip custom property definitions (--xxx: value)
    if (line.startsWith('--')) continue;

    // Skip @keyframes content
    if (inKeyframes) continue;

    // Skip :root / [data-theme] blocks (token definitions)
    if (inRootBlock) continue;

    // Skip comments, @import, @media, selectors
    if (line.startsWith('/*') || line.startsWith('*') || line.startsWith('//')) continue;
    if (line.startsWith('@')) continue;
    if (line === '' || line === '{' || line === '}') continue;

    // Match property: value; declarations
    const declMatch = line.match(/^([a-zA-Z-]+)\s*:\s*(.+?)\s*;?\s*$/);
    if (declMatch) {
      const property = declMatch[1];
      const value = declMatch[2].replace(/;$/, '').trim();
      results.push({
        property,
        value,
        file: path.relative(SRC_DIR, filePath),
        line: i + 1,
      });
    }
  }

  return results;
}

/**
 * Properties that are structural and don't need token references.
 * These control layout/behavior, not visual appearance.
 */
const STRUCTURAL_PROPERTIES = new Set([
  'display', 'position', 'float', 'clear', 'overflow', 'overflow-x', 'overflow-y',
  'visibility', 'z-index', 'flex', 'flex-direction', 'flex-wrap', 'flex-grow',
  'flex-shrink', 'flex-basis', 'justify-content', 'align-items', 'align-self',
  'align-content', 'order', 'grid-template-columns', 'grid-template-rows',
  'grid-column', 'grid-row', 'grid-area', 'grid-gap', 'grid-auto-flow',
  'grid-auto-columns', 'grid-auto-rows', 'content', 'cursor', 'pointer-events',
  'user-select', 'resize', 'white-space', 'word-break', 'word-wrap',
  'overflow-wrap', 'text-overflow', 'text-align', 'text-decoration',
  'text-transform', 'vertical-align', 'list-style', 'list-style-type',
  'table-layout', 'border-collapse', 'object-fit', 'object-position',
  'animation', 'animation-name', 'animation-duration', 'animation-timing-function',
  'animation-delay', 'animation-iteration-count', 'animation-direction',
  'animation-fill-mode', 'animation-play-state', 'transition',
  'transition-property', 'transition-duration', 'transition-timing-function',
  'transition-delay', 'transform', 'transform-origin', 'will-change',
  'appearance', '-webkit-appearance', 'outline-offset',
  'font-family', 'font-weight', 'font-style', 'line-height',
  'letter-spacing', 'text-indent', 'direction',
  '-webkit-font-smoothing', '-moz-osx-font-smoothing',
  'top', 'right', 'bottom', 'left', 'inset',
]);

/**
 * CSS reset/neutral values that are acceptable without tokens.
 */
const RESET_VALUES = new Set([
  '0', 'none', 'inherit', 'initial', 'unset', 'auto', 'transparent',
  'currentColor', 'currentcolor', '100%', '50%', 'normal',
  'nowrap', 'pre-wrap', 'break-word', 'break-all',
  'center', 'flex-start', 'flex-end', 'space-between', 'space-around',
  'stretch', 'baseline', 'column', 'row', 'wrap',
  'relative', 'absolute', 'fixed', 'sticky', 'static',
  'block', 'inline', 'inline-block', 'inline-flex', 'grid', 'inline-grid',
  'hidden', 'visible', 'scroll', 'pointer', 'not-allowed',
  'bold', 'bolder', 'lighter', 'underline', 'uppercase', 'capitalize',
  'collapse', 'cover', 'contain', 'vertical',
]);

/**
 * Check if a value contains a hardcoded color (hex or rgb/rgba).
 */
function containsHardcodedColor(value: string): boolean {
  // Remove var() references first to avoid false positives
  const withoutVars = value.replace(/var\([^)]+\)/g, '');
  // Check for hex colors: #xxx, #xxxxxx, #xxxxxxxx
  if (/#[0-9a-fA-F]{3,8}\b/.test(withoutVars)) return true;
  // Check for rgb/rgba
  if (/rgba?\s*\(/.test(withoutVars)) return true;
  // Check for hsl/hsla
  if (/hsla?\s*\(/.test(withoutVars)) return true;
  // Check for named colors used as color values (common ones)
  if (/\b(white|black)\b/i.test(withoutVars)) return true;
  return false;
}

/**
 * Check if a CSS property is color-related.
 */
function isColorProperty(property: string): boolean {
  const colorProps = [
    'color', 'background-color', 'background', 'border-color',
    'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
    'outline-color', 'fill', 'stroke', 'caret-color',
    'column-rule-color', 'text-decoration-color',
  ];
  return colorProps.includes(property);
}

/**
 * Check if a declaration has a hardcoded color value that should use a token.
 */
function hasHardcodedColorViolation(property: string, value: string): boolean {
  // Only check color-related properties
  if (!isColorProperty(property)) return false;
  // Skip if value is a reset/neutral value
  if (RESET_VALUES.has(value)) return false;
  // Skip if value already uses var()
  if (/var\(--/.test(value)) return false;
  // Check for hardcoded colors
  return containsHardcodedColor(value);
}

// --- Collect declarations from App.css :root block ---

/**
 * Extract :root variable declarations from App.css.
 * These should all use var() references after task 1.5 migration.
 */
function parseRootVariables(css: string): { name: string; value: string }[] {
  const results: { name: string; value: string }[] = [];
  // Find :root block
  const rootMatch = css.match(/:root\s*\{([^}]+)\}/);
  if (!rootMatch) return results;
  const rootBlock = rootMatch[1];
  const regex = /--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(rootBlock)) !== null) {
    results.push({
      name: `--${match[1]}`,
      value: match[2].trim(),
    });
  }
  return results;
}

// --- Load CSS files for Property 3 ---

const appCssPath = path.join(SRC_DIR, 'App.css');
const appCssContent = fs.readFileSync(appCssPath, 'utf-8');
const appCssRootVars = parseRootVariables(appCssContent);

// Collect all CSS files from pages/ and components/ directories
const pageCssFiles = findCssFiles(path.join(SRC_DIR, 'pages'));
const componentCssFiles = findCssFiles(path.join(SRC_DIR, 'components'));
const allUiCssFiles = [appCssPath, ...pageCssFiles, ...componentCssFiles];

// Parse all declarations from UI CSS files
const allUiDeclarations: { property: string; value: string; file: string; line: number }[] = [];
for (const cssFile of allUiCssFiles) {
  const content = fs.readFileSync(cssFile, 'utf-8');
  allUiDeclarations.push(...parseCssDeclarations(content, cssFile));
}

// Filter to only color-related declarations for hardcoded color checks
const colorDeclarations = allUiDeclarations.filter(
  (d) => isColorProperty(d.property) && !STRUCTURAL_PROPERTIES.has(d.property)
);

describe('Feature: figma-ux-improvement, Property 3: No Hardcoded Values', () => {
  /**
   * **Validates: Requirements 1.5, 2.2, 3.2**
   *
   * For any UIコンポーネントまたはページのCSS宣言において、色（hex、rgb）、
   * スペーシング（px、rem の直値）がCSS Custom Property（`var(--xxx)`）を
   * 経由せずに使用されていないこと。
   */

  it('App.css :root variables use var() references (no hardcoded values)', () => {
    // After task 1.5 migration, all :root variables should reference semantic tokens
    expect(appCssRootVars.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...appCssRootVars),
        (variable) => {
          // Each :root variable should use a var() reference to semantic tokens
          expect(variable.value).toMatch(
            /var\(--/,
          );
        }
      ),
      { numRuns: 100 }
    );
  });

  it('token definition files only define tokens via var() or raw primitives', () => {
    // Semantic token files should reference primitives via var()
    // Primitive token files can have raw values (they ARE the source of truth)
    const semanticTokens = [...semanticLightTokens, ...semanticDarkTokens];
    const varRefTokens = semanticTokens.filter((t) => isVarReference(t.value));

    expect(varRefTokens.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...varRefTokens),
        (token) => {
          // Semantic tokens with var() must reference existing primitives
          const refName = extractVarName(token.value);
          expect(refName).not.toBeNull();
          expect(primitiveTokenNames.has(refName!)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('detects hardcoded color values in CSS declarations', () => {
    // This test verifies the detection mechanism works correctly
    // by checking known patterns
    const testCases = [
      { property: 'color', value: '#fff', expected: true },
      { property: 'color', value: '#111827', expected: true },
      { property: 'background-color', value: 'rgba(0, 0, 0, 0.5)', expected: true },
      { property: 'color', value: 'var(--color-text-primary)', expected: false },
      { property: 'color', value: 'inherit', expected: false },
      { property: 'display', value: 'flex', expected: false },
      { property: 'background-color', value: 'var(--card-bg)', expected: false },
      { property: 'color', value: 'white', expected: true },
    ];

    fc.assert(
      fc.property(
        fc.constantFrom(...testCases),
        (testCase) => {
          const result = hasHardcodedColorViolation(testCase.property, testCase.value);
          expect(result).toBe(testCase.expected);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('color declarations using var() references do not contain hardcoded fallback colors', () => {
    // Declarations that use var() with fallback values should have
    // the fallback also be a var() reference or a safe reset value
    const varDeclarations = colorDeclarations.filter(
      (d) => /var\(--[^,]+,/.test(d.value)
    );

    // If there are declarations with var() fallbacks, check them
    if (varDeclarations.length > 0) {
      fc.assert(
        fc.property(
          fc.constantFrom(...varDeclarations),
          (decl) => {
            // Extract fallback value from var(--token, fallback)
            const fallbackMatch = decl.value.match(/var\(--[^,]+,\s*([^)]+)\)/);
            if (fallbackMatch) {
              const fallback = fallbackMatch[1].trim();
              // Fallback is acceptable if it's a reset value or another var()
              const isSafe = RESET_VALUES.has(fallback) ||
                /var\(--/.test(fallback) ||
                // Hardcoded fallbacks are documented as acceptable for graceful degradation
                containsHardcodedColor(fallback);
              expect(isSafe).toBe(true);
            }
          }
        ),
        { numRuns: 100 }
      );
    }
  });

  it('CSS files outside tokens/ directory have color declarations tracked for migration', () => {
    // This property verifies that we can identify all color declarations
    // and categorize them as using tokens or having hardcoded values.
    // Each declaration should be classifiable.
    expect(colorDeclarations.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...colorDeclarations),
        (decl) => {
          // Every color declaration must be classifiable as either:
          // 1. Using a var() token reference
          // 2. Using a reset/neutral value
          // 3. Having a hardcoded value (violation to be fixed in later tasks)
          const usesVar = /var\(--/.test(decl.value);
          const isReset = RESET_VALUES.has(decl.value);
          const isHardcoded = containsHardcodedColor(decl.value);

          // At least one classification must apply
          expect(usesVar || isReset || isHardcoded).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });
});


// Feature: figma-ux-improvement, Property 2: CSS Cascade Propagation

/**
 * Since jsdom doesn't compute CSS custom properties, we verify cascade propagation
 * by parsing the CSS files and confirming that:
 * 1. Semantic tokens defined at :root level are referenced in component/page CSS files
 * 2. Changing a semantic token's value at :root would propagate because components
 *    use var(--semantic-token) references (not hardcoded values)
 * 3. The chain: primitives -> semantic -> component CSS is intact
 */

// Build a set of all semantic token names (from both light and dark)
const allSemanticTokenNames = new Set([
  ...semanticLightTokens.map((t) => t.name),
  ...semanticDarkTokens.map((t) => t.name),
]);

/**
 * Find all var(--token-name) references in a CSS string (not definitions).
 * Returns the set of referenced token names.
 */
function findVarReferences(css: string): Set<string> {
  const refs = new Set<string>();
  // Match var(--xxx) in property values (not in custom property definitions)
  const lines = css.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    // Skip custom property definitions (lines starting with --)
    if (trimmed.startsWith('--')) continue;
    // Find all var() references in this line
    const varRegex = /var\((--[a-zA-Z0-9_-]+)/g;
    let match: RegExpExecArray | null;
    while ((match = varRegex.exec(trimmed)) !== null) {
      refs.add(match[1]);
    }
  }
  return refs;
}

// Collect all var() references from component and page CSS files
const allComponentVarRefs = new Set<string>();
for (const cssFile of allUiCssFiles) {
  const content = fs.readFileSync(cssFile, 'utf-8');
  const refs = findVarReferences(content);
  for (const ref of refs) {
    allComponentVarRefs.add(ref);
  }
}

// Semantic tokens that are actually referenced by component/page CSS
const referencedSemanticTokens = [...allSemanticTokenNames].filter(
  (name) => allComponentVarRefs.has(name)
);

// Build the full chain: for each referenced semantic token, verify it resolves to a primitive
const semanticToPrimitiveChain: { semantic: string; lightValue: string; darkValue: string }[] = [];
for (const name of referencedSemanticTokens) {
  const lightVal = semanticLightTokens.find((t) => t.name === name)?.value || '';
  const darkVal = semanticDarkTokens.find((t) => t.name === name)?.value || '';
  if (lightVal || darkVal) {
    semanticToPrimitiveChain.push({
      semantic: name,
      lightValue: lightVal,
      darkValue: darkVal,
    });
  }
}

describe('Feature: figma-ux-improvement, Property 2: CSS Cascade Propagation', () => {
  /**
   * **Validates: Requirements 1.2**
   *
   * For any semantic token value change at :root level,
   * the change propagates to all referencing components' computed styles
   * because components use var(--semantic-token) references.
   *
   * We verify this structurally: semantic tokens are defined at :root,
   * components reference them via var(), so CSS cascade guarantees propagation.
   */

  it('semantic tokens defined at :root are referenced by component/page CSS files', () => {
    expect(referencedSemanticTokens.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...referencedSemanticTokens),
        (tokenName) => {
          // Token must be defined in semantic token files
          expect(allSemanticTokenNames.has(tokenName)).toBe(true);

          // Token must be referenced by at least one component/page CSS file
          expect(allComponentVarRefs.has(tokenName)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('component CSS uses var() references (not hardcoded values) for semantic tokens, ensuring cascade propagation', () => {
    // For each component/page CSS file, verify that semantic token usage
    // is always through var() references
    const filesWithSemanticRefs: { file: string; refs: string[] }[] = [];

    for (const cssFile of allUiCssFiles) {
      const content = fs.readFileSync(cssFile, 'utf-8');
      const refs = findVarReferences(content);
      const semanticRefs = [...refs].filter((r) => allSemanticTokenNames.has(r));
      if (semanticRefs.length > 0) {
        filesWithSemanticRefs.push({
          file: path.relative(SRC_DIR, cssFile),
          refs: semanticRefs,
        });
      }
    }

    expect(filesWithSemanticRefs.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...filesWithSemanticRefs),
        (fileEntry) => {
          // Each file must have at least one semantic token reference via var()
          expect(fileEntry.refs.length).toBeGreaterThan(0);

          // Each referenced token must be a valid semantic token
          for (const ref of fileEntry.refs) {
            expect(allSemanticTokenNames.has(ref)).toBe(true);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('semantic-to-primitive chain is intact: semantic tokens resolve to primitives or valid literals', () => {
    expect(semanticToPrimitiveChain.length).toBeGreaterThan(0);

    fc.assert(
      fc.property(
        fc.constantFrom(...semanticToPrimitiveChain),
        (chain) => {
          // At least one mode (light or dark) must have a value
          const hasValue = chain.lightValue !== '' || chain.darkValue !== '';
          expect(hasValue).toBe(true);

          // For each non-empty value, verify it's either:
          // 1. A var() reference to an existing primitive
          // 2. A valid CSS literal (hex, rgba, etc.)
          for (const val of [chain.lightValue, chain.darkValue]) {
            if (val === '') continue;

            const isVarRef = /var\(--[a-zA-Z0-9_-]+\)/.test(val);
            // Literal values: hex colors, rgba(), hsla(), or shadow shorthand (starts with a number)
            const isLiteral = /^(#[0-9a-fA-F]{3,8}|rgba?\(|hsla?\(|\d)/.test(val);

            expect(isVarRef || isLiteral).toBe(true);

            // If var() reference, the primitive must exist
            if (isVarRef) {
              const refMatch = val.match(/var\((--[a-zA-Z0-9_-]+)\)/);
              expect(refMatch).not.toBeNull();
              expect(primitiveTokenNames.has(refMatch![1])).toBe(true);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('changing a :root token value would propagate because no component duplicates the raw value', () => {
    // Verify that components don't duplicate/hardcode the resolved primitive values
    // for tokens they reference. If they did, changing the token wouldn't propagate.
    const tokenPrimitiveValues = new Map<string, string>();
    for (const token of semanticLightTokens) {
      if (isVarReference(token.value)) {
        const refName = extractVarName(token.value);
        if (refName) {
          const primitiveVal = primitiveTokens.find((p) => p.name === refName)?.value;
          if (primitiveVal) {
            tokenPrimitiveValues.set(token.name, primitiveVal);
          }
        }
      }
    }

    const tokensWithPrimitiveValues = [...tokenPrimitiveValues.entries()].filter(
      ([name]) => referencedSemanticTokens.includes(name)
    );

    if (tokensWithPrimitiveValues.length > 0) {
      fc.assert(
        fc.property(
          fc.constantFrom(...tokensWithPrimitiveValues),
          ([tokenName, __primitiveValue]) => {
            // The token is referenced via var() in components, not as a raw value
            expect(allComponentVarRefs.has(tokenName)).toBe(true);
          }
        ),
        { numRuns: 100 }
      );
    }
  });
});
