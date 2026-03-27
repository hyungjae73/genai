import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

// Feature: figma-ux-improvement, Property 11: Component Mapping Validity

/**
 * Component mapping data structure matching the Figma ↔ Code mapping document.
 */
interface ComponentMappingEntry {
  figmaName: string;
  codePath: string;
  status: 'synced' | 'outdated' | 'new';
}

const VALID_STATUSES = ['synced', 'outdated', 'new'] as const;

/**
 * The actual component mapping entries from the project.
 * This mirrors the mapping table in figma/component-mapping.md.
 */
const componentMappings: ComponentMappingEntry[] = [
  { figmaName: 'Button', codePath: 'components/ui/Button/Button.tsx', status: 'synced' },
  { figmaName: 'Badge', codePath: 'components/ui/Badge/Badge.tsx', status: 'synced' },
  { figmaName: 'Card', codePath: 'components/ui/Card/Card.tsx', status: 'synced' },
  { figmaName: 'Table', codePath: 'components/ui/Table/Table.tsx', status: 'synced' },
  { figmaName: 'Modal', codePath: 'components/ui/Modal/Modal.tsx', status: 'synced' },
  { figmaName: 'Input', codePath: 'components/ui/Input/Input.tsx', status: 'synced' },
  { figmaName: 'Select', codePath: 'components/ui/Select/Select.tsx', status: 'synced' },
  { figmaName: 'Sidebar', codePath: 'components/ui/Sidebar/Sidebar.tsx', status: 'synced' },
  { figmaName: 'ThemeToggle', codePath: 'components/ui/ThemeToggle/ThemeToggle.tsx', status: 'synced' },
];

/**
 * Validates a single component mapping entry.
 */
function validateMappingEntry(entry: ComponentMappingEntry): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (!entry.figmaName || entry.figmaName.trim() === '') {
    errors.push('figmaName is empty');
  }
  if (!entry.codePath || entry.codePath.trim() === '') {
    errors.push('codePath is empty');
  }
  if (!entry.status || !VALID_STATUSES.includes(entry.status)) {
    errors.push(`status "${entry.status}" is not a valid value (expected: synced, outdated, new)`);
  }

  return { valid: errors.length === 0, errors };
}

describe('Property 11: Component Mapping Validity', () => {
  /**
   * Validates: Requirements 6.4
   *
   * For any component mapping entry, figmaName, codePath, and status fields
   * must be non-empty, and status must be one of 'synced', 'outdated', or 'new'.
   */
  it('all actual mapping entries have valid figmaName, codePath, and status', () => {
    for (const entry of componentMappings) {
      const result = validateMappingEntry(entry);
      expect(result.valid, `Invalid entry: ${JSON.stringify(entry)} - ${result.errors.join(', ')}`).toBe(true);
    }
  });

  /**
   * Validates: Requirements 6.4
   *
   * Property-based test: for any randomly generated mapping entry with valid fields,
   * the validation function correctly accepts it. For entries with invalid fields,
   * the validation function correctly rejects them.
   */
  it('validateMappingEntry accepts entries with non-empty fields and valid status', () => {
    const validEntryArb = fc.record({
      figmaName: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      codePath: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      status: fc.constantFrom<'synced' | 'outdated' | 'new'>('synced', 'outdated', 'new'),
    });

    fc.assert(
      fc.property(validEntryArb, (entry: ComponentMappingEntry) => {
        const result = validateMappingEntry(entry);
        expect(result.valid).toBe(true);
        expect(result.errors).toHaveLength(0);
      }),
      { numRuns: 100 }
    );
  });

  it('validateMappingEntry rejects entries with empty figmaName', () => {
    const emptyFigmaNameArb = fc.record({
      figmaName: fc.constantFrom('', '   '),
      codePath: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      status: fc.constantFrom<'synced' | 'outdated' | 'new'>('synced', 'outdated', 'new'),
    });

    fc.assert(
      fc.property(emptyFigmaNameArb, (entry: ComponentMappingEntry) => {
        const result = validateMappingEntry(entry);
        expect(result.valid).toBe(false);
        expect(result.errors.some(e => e.includes('figmaName'))).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('validateMappingEntry rejects entries with empty codePath', () => {
    const emptyCodePathArb = fc.record({
      figmaName: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      codePath: fc.constantFrom('', '   '),
      status: fc.constantFrom<'synced' | 'outdated' | 'new'>('synced', 'outdated', 'new'),
    });

    fc.assert(
      fc.property(emptyCodePathArb, (entry: ComponentMappingEntry) => {
        const result = validateMappingEntry(entry);
        expect(result.valid).toBe(false);
        expect(result.errors.some(e => e.includes('codePath'))).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('validateMappingEntry rejects entries with invalid status', () => {
    const invalidStatusArb = fc.record({
      figmaName: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      codePath: fc.string({ minLength: 1 }).filter(s => s.trim().length > 0),
      status: fc.string({ minLength: 1 })
        .filter(s => !VALID_STATUSES.includes(s as any)) as fc.Arbitrary<any>,
    });

    fc.assert(
      fc.property(invalidStatusArb, (entry: ComponentMappingEntry) => {
        const result = validateMappingEntry(entry);
        expect(result.valid).toBe(false);
        expect(result.errors.some(e => e.includes('status'))).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it('all 9 UI components are present in the mapping', () => {
    const expectedComponents = [
      'Button', 'Badge', 'Card', 'Table', 'Modal',
      'Input', 'Select', 'Sidebar', 'ThemeToggle',
    ];

    expect(componentMappings).toHaveLength(expectedComponents.length);

    for (const name of expectedComponents) {
      const found = componentMappings.find(m => m.figmaName === name);
      expect(found, `Missing mapping for component: ${name}`).toBeDefined();
    }
  });

  it('no duplicate figmaName entries exist in the mapping', () => {
    const names = componentMappings.map(m => m.figmaName);
    const uniqueNames = new Set(names);
    expect(uniqueNames.size).toBe(names.length);
  });
});
