// Feature: figma-ux-improvement, Property 4: Accessibility Attributes

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render, cleanup } from '@testing-library/react';
import React from 'react';
import { Button } from '../components/ui/Button/Button';
import { Input } from '../components/ui/Input/Input';
import { Select } from '../components/ui/Select/Select';

// --- Arbitrary generators ---

const arbButtonVariant = fc.constantFrom('primary' as const, 'secondary' as const, 'danger' as const, 'ghost' as const);
const arbButtonSize = fc.constantFrom('sm' as const, 'md' as const, 'lg' as const);
const arbBoolean = fc.boolean();
const arbLabel = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,20}$/);
const arbAriaLabel = fc.option(fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,20}$/));

const arbInputType = fc.constantFrom('text' as const, 'url' as const, 'email' as const, 'search' as const);
const arbOptionalError = fc.option(fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,30}$/));
const arbOptionalPlaceholder = fc.option(fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,20}$/));

const arbSelectOption = fc.record({
  value: fc.stringMatching(/^[a-z]{1,10}$/),
  label: fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,15}$/),
});
const arbSelectOptions = fc.array(arbSelectOption, { minLength: 1, maxLength: 10 });

// --- Property 4: Accessibility Attributes ---

describe('Feature: figma-ux-improvement, Property 4: Accessibility Attributes', () => {
  /**
   * **Validates: Requirements 2.4**
   *
   * For any interactive UI component (Button, Input, Select) with any props combination,
   * the rendered output must contain appropriate ARIA attributes (role, aria-label, etc.)
   * and be keyboard-focusable.
   */

  it('Button: has implicit button role and is keyboard-focusable for any props combination', () => {
    fc.assert(
      fc.property(
        arbButtonVariant,
        arbButtonSize,
        arbBoolean,
        arbBoolean,
        arbAriaLabel,
        (variant, size, disabled, loading, ariaLabel) => {
          cleanup();
          const { container } = render(
            <Button
              variant={variant}
              size={size}
              disabled={disabled}
              loading={loading}
              aria-label={ariaLabel ?? undefined}
            >
              Click
            </Button>
          );

          const button = container.querySelector('button');
          expect(button).not.toBeNull();

          // Button should be a <button> element (implicit role="button")
          expect(button!.tagName).toBe('BUTTON');

          // If aria-label is provided, it should be set
          if (ariaLabel) {
            expect(button!.getAttribute('aria-label')).toBe(ariaLabel);
          }

          // When loading, aria-busy should be set
          if (loading) {
            expect(button!.getAttribute('aria-busy')).toBe('true');
          }

          // When disabled or loading, aria-disabled should be set
          if (disabled || loading) {
            expect(button!.getAttribute('aria-disabled')).toBe('true');
          }

          // Button should have a type attribute
          expect(button!.getAttribute('type')).toBe('button');

          // Button should be focusable (has no tabindex=-1)
          const tabIndex = button!.getAttribute('tabindex');
          expect(tabIndex !== '-1').toBe(true);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Input: has associated label and is keyboard-focusable for any props combination', () => {
    fc.assert(
      fc.property(
        arbLabel,
        arbInputType,
        arbOptionalError,
        arbOptionalPlaceholder,
        (label, type, error, placeholder) => {
          cleanup();
          const { container } = render(
            <Input
              label={label}
              type={type}
              value=""
              onChange={() => {}}
              error={error ?? undefined}
              placeholder={placeholder ?? undefined}
            />
          );

          // Input should exist
          const input = container.querySelector('input');
          expect(input).not.toBeNull();
          expect(input!.tagName).toBe('INPUT');

          // Input should have correct type
          expect(input!.getAttribute('type')).toBe(type);

          // Input should be focusable (no tabindex=-1)
          const tabIndex = input!.getAttribute('tabindex');
          expect(tabIndex !== '-1').toBe(true);

          // Label should be associated via htmlFor/id
          const inputId = input!.getAttribute('id');
          expect(inputId).toBeTruthy();
          const labelEl = container.querySelector(`label[for="${inputId}"]`);
          expect(labelEl).not.toBeNull();
          expect(labelEl!.textContent).toBe(label);

          // When error is present, aria-invalid should be set
          if (error) {
            expect(input!.getAttribute('aria-invalid')).toBe('true');

            // Error message should have role="alert"
            const alert = container.querySelector('[role="alert"]');
            expect(alert).not.toBeNull();
            expect(alert!.textContent).toContain(error);

            // aria-describedby should reference the error element
            const describedBy = input!.getAttribute('aria-describedby');
            expect(describedBy).toBeTruthy();
          }

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Select: has associated label and is keyboard-focusable for any props combination', () => {
    fc.assert(
      fc.property(
        arbLabel,
        arbSelectOptions,
        arbAriaLabel,
        (label, options, ariaLabel) => {
          cleanup();
          const selectedValue = options[0].value;

          const { container } = render(
            <Select
              label={label}
              value={selectedValue}
              onChange={() => {}}
              options={options}
              aria-label={ariaLabel ?? undefined}
            />
          );

          // Select element should exist
          const select = container.querySelector('select');
          expect(select).not.toBeNull();
          expect(select!.tagName).toBe('SELECT');

          // Select should be focusable (no tabindex=-1)
          const tabIndex = select!.getAttribute('tabindex');
          expect(tabIndex !== '-1').toBe(true);

          // Label should be associated via htmlFor/id
          const selectId = select!.getAttribute('id');
          expect(selectId).toBeTruthy();
          const labelEl = container.querySelector(`label[for="${selectId}"]`);
          expect(labelEl).not.toBeNull();
          expect(labelEl!.textContent).toBe(label);

          // If aria-label is provided, it should be set
          if (ariaLabel) {
            expect(select!.getAttribute('aria-label')).toBe(ariaLabel);
          }

          // All options should be rendered
          const renderedOptions = select!.querySelectorAll('option');
          expect(renderedOptions.length).toBe(options.length);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });
});


// Feature: figma-ux-improvement, Property 9: Touch Target Size

import fs from 'fs';
import path from 'path';

// --- Property 9: Touch Target Size ---

describe('Feature: figma-ux-improvement, Property 9: Touch Target Size', () => {
  /**
   * **Validates: Requirements 5.3**
   *
   * For any interactive element (button, input, select) with any variant/size combination,
   * the rendered element must have CSS classes that enforce min-height >= 44px.
   * Since jsdom doesn't compute actual pixel sizes, we verify:
   * 1. The correct CSS classes are applied to interactive elements
   * 2. The corresponding CSS files declare min-height >= 44px for those classes
   */

  // Helper: parse min-height value from CSS content for a given class name
  function getMinHeightForClass(cssContent: string, className: string): number | undefined {
    // Escape dots for regex and build a pattern that finds the class selector block
    const escaped = className.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Match the selector containing the class name, then find min-height in its block
    const blockRegex = new RegExp(escaped + '\\s*\\{([^}]*?)\\}', 'g');
    let match;
    while ((match = blockRegex.exec(cssContent)) !== null) {
      const block = match[1];
      const minHeightMatch = block.match(/min-height:\s*(\d+)px/);
      if (minHeightMatch) {
        return parseInt(minHeightMatch[1], 10);
      }
    }
    return undefined;
  }

  // Read CSS files once for static verification
  const buttonCssPath = path.resolve(__dirname, '../components/ui/Button/Button.css');
  const inputCssPath = path.resolve(__dirname, '../components/ui/Input/Input.css');
  const selectCssPath = path.resolve(__dirname, '../components/ui/Select/Select.css');
  const modalCssPath = path.resolve(__dirname, '../components/ui/Modal/Modal.css');

  const buttonCss = fs.readFileSync(buttonCssPath, 'utf-8');
  const inputCss = fs.readFileSync(inputCssPath, 'utf-8');
  const selectCss = fs.readFileSync(selectCssPath, 'utf-8');
  const modalCss = fs.readFileSync(modalCssPath, 'utf-8');

  it('Button: CSS classes enforcing min-height >= 44px are applied for any variant/size', () => {
    fc.assert(
      fc.property(
        arbButtonVariant,
        arbButtonSize,
        arbBoolean,
        arbBoolean,
        (variant, size, disabled, loading) => {
          cleanup();
          const { container } = render(
            <Button
              variant={variant}
              size={size}
              disabled={disabled}
              loading={loading}
            >
              Click
            </Button>
          );

          const button = container.querySelector('button');
          expect(button).not.toBeNull();

          // Verify the size class is applied
          const sizeClass = `btn--${size}`;
          expect(button!.classList.contains(sizeClass)).toBe(true);
          expect(button!.classList.contains('btn')).toBe(true);

          // Verify the CSS file declares min-height >= 44px for this size class
          const minHeight = getMinHeightForClass(buttonCss, `.${sizeClass}`);
          expect(minHeight).toBeDefined();
          expect(minHeight!).toBeGreaterThanOrEqual(44);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Input: CSS class enforcing min-height >= 44px is applied for any props', () => {
    fc.assert(
      fc.property(
        arbLabel,
        arbInputType,
        arbOptionalError,
        arbOptionalPlaceholder,
        (label, type, error, placeholder) => {
          cleanup();
          const { container } = render(
            <Input
              label={label}
              type={type}
              value=""
              onChange={() => {}}
              error={error ?? undefined}
              placeholder={placeholder ?? undefined}
            />
          );

          const input = container.querySelector('input');
          expect(input).not.toBeNull();

          // Verify the input has the correct CSS class
          expect(input!.classList.contains('input-field__input')).toBe(true);

          // Verify the CSS file declares min-height >= 44px for the input class
          const minHeight = getMinHeightForClass(inputCss, '.input-field__input');
          expect(minHeight).toBeDefined();
          expect(minHeight!).toBeGreaterThanOrEqual(44);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Select: CSS class enforcing min-height >= 44px is applied for any props', () => {
    fc.assert(
      fc.property(
        arbLabel,
        arbSelectOptions,
        arbAriaLabel,
        (label, options, ariaLabel) => {
          cleanup();
          const selectedValue = options[0].value;

          const { container } = render(
            <Select
              label={label}
              value={selectedValue}
              onChange={() => {}}
              options={options}
              aria-label={ariaLabel ?? undefined}
            />
          );

          const select = container.querySelector('select');
          expect(select).not.toBeNull();

          // Verify the select has the correct CSS class
          expect(select!.classList.contains('select-field__select')).toBe(true);

          // Verify the CSS file declares min-height >= 44px for the select class
          const minHeight = getMinHeightForClass(selectCss, '.select-field__select');
          expect(minHeight).toBeDefined();
          expect(minHeight!).toBeGreaterThanOrEqual(44);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Modal close button: CSS declares min-width and min-height >= 44px', () => {
    // Static verification that the modal close button CSS enforces touch target size
    const closeMinHeight = getMinHeightForClass(modalCss, '.modal__close');
    expect(closeMinHeight).toBeDefined();
    expect(closeMinHeight!).toBeGreaterThanOrEqual(44);

    // Also verify min-width >= 44px
    const minWidthRegex = /\.modal__close\s*\{[^}]*min-width:\s*(\d+)px/;
    const minWidthMatch = modalCss.match(minWidthRegex);
    expect(minWidthMatch).not.toBeNull();
    expect(parseInt(minWidthMatch![1], 10)).toBeGreaterThanOrEqual(44);
  });
});


// Feature: figma-ux-improvement, Property 10: Table Mobile Layout

import { Table } from '../components/ui/Table/Table';

// --- Arbitrary generators for Table ---

const arbColumnKey = fc.stringMatching(/^[a-z]{1,8}$/);
const arbColumnHeader = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,15}$/);

const arbColumn = fc.record({
  key: arbColumnKey,
  header: arbColumnHeader,
});

// Generate columns with unique keys
const arbColumns = fc
  .array(arbColumn, { minLength: 1, maxLength: 6 })
  .map((cols) => {
    const seen = new Set<string>();
    return cols.filter((c) => {
      if (seen.has(c.key)) return false;
      seen.add(c.key);
      return true;
    });
  })
  .filter((cols) => cols.length > 0);

// Generate a row as Record<string, unknown> based on column keys
const arbRowForColumns = (columns: { key: string; header: string }[]) =>
  fc.record(
    Object.fromEntries(
      columns.map((col) => [col.key, fc.stringMatching(/^[A-Za-z0-9 ]{0,20}$/)])
    )
  ) as fc.Arbitrary<Record<string, unknown>>;

const arbMobileLayout = fc.constantFrom('card' as const, 'scroll' as const);
const arbTableAriaLabel = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,20}$/);

// --- Property 10: Table Mobile Layout ---

describe('Feature: figma-ux-improvement, Property 10: Table Mobile Layout', () => {
  /**
   * **Validates: Requirements 5.5**
   *
   * For any Table component, when mobileLayout is 'card' the wrapper has class
   * 'table-wrapper--mobile-card' and a card view (role="list") exists; when 'scroll'
   * the wrapper has class 'table-wrapper--mobile-scroll' and no card-mode class is applied.
   * Also verifies the CSS file contains the correct media query rules.
   */

  it('Table renders correct wrapper class and structure for any mobileLayout, columns, and data', () => {
    fc.assert(
      fc.property(
        arbColumns,
        arbMobileLayout,
        arbTableAriaLabel,
        fc.boolean(),
        (columns, mobileLayout, ariaLabel, hasData) => {
          cleanup();

          // Generate data rows based on columns
          const data = hasData
            ? columns.map((col) =>
                Object.fromEntries(columns.map((c) => [c.key, `val-${c.key}`]))
              )
            : [];

          // Skip empty data case — Table renders a different structure when empty
          if (data.length === 0) {
            cleanup();
            return;
          }

          const { container } = render(
            <Table
              columns={columns}
              data={data}
              mobileLayout={mobileLayout}
              aria-label={ariaLabel}
            />
          );

          const wrapper = container.querySelector('.table-wrapper');
          expect(wrapper).not.toBeNull();

          if (mobileLayout === 'card') {
            // Card mode: wrapper should have the card class
            expect(wrapper!.classList.contains('table-wrapper--mobile-card')).toBe(true);
            expect(wrapper!.classList.contains('table-wrapper--mobile-scroll')).toBe(false);

            // Card view (role="list") should exist in the DOM
            const cardView = wrapper!.querySelector('[role="list"]');
            expect(cardView).not.toBeNull();

            // Each data row should have a corresponding card (role="listitem")
            const cardItems = wrapper!.querySelectorAll('[role="listitem"]');
            expect(cardItems.length).toBe(data.length);
          } else {
            // Scroll mode: wrapper should have the scroll class
            expect(wrapper!.classList.contains('table-wrapper--mobile-scroll')).toBe(true);
            expect(wrapper!.classList.contains('table-wrapper--mobile-card')).toBe(false);
          }

          // In both modes, the <table> element should exist in the DOM
          const tableEl = wrapper!.querySelector('table');
          expect(tableEl).not.toBeNull();
          expect(tableEl!.getAttribute('aria-label')).toBe(ariaLabel);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('Table renders with randomly generated data and verifies card/scroll structure', () => {
    fc.assert(
      fc.property(
        arbColumns.chain((columns) =>
          fc.tuple(
            fc.constant(columns),
            fc.array(arbRowForColumns(columns), { minLength: 1, maxLength: 10 }),
            arbMobileLayout,
            arbTableAriaLabel
          )
        ),
        ([columns, data, mobileLayout, ariaLabel]) => {
          cleanup();

          const { container } = render(
            <Table
              columns={columns}
              data={data}
              mobileLayout={mobileLayout}
              aria-label={ariaLabel}
            />
          );

          const wrapper = container.querySelector('.table-wrapper');
          expect(wrapper).not.toBeNull();

          // Verify correct class is applied
          const expectedClass = `table-wrapper--mobile-${mobileLayout}`;
          expect(wrapper!.classList.contains(expectedClass)).toBe(true);

          if (mobileLayout === 'card') {
            // Card view should have list items matching data length
            const listItems = wrapper!.querySelectorAll('[role="listitem"]');
            expect(listItems.length).toBe(data.length);

            // Each card should have fields matching column count
            listItems.forEach((item) => {
              const fields = item.querySelectorAll('.table-card__field');
              expect(fields.length).toBe(columns.length);
            });
          }

          // Table rows should match data length
          const tableRows = wrapper!.querySelectorAll('tbody tr');
          expect(tableRows.length).toBe(data.length);

          cleanup();
        }
      ),
      { numRuns: 100 }
    );
  });

  it('CSS file contains correct media query rules for card and scroll modes', () => {
    const tableCssPath = path.resolve(__dirname, '../components/ui/Table/Table.css');
    const tableCss = fs.readFileSync(tableCssPath, 'utf-8');

    // Card mode: media query should hide the table and show cards
    expect(tableCss).toContain('.table-wrapper--mobile-card .table');
    expect(tableCss).toContain('.table-wrapper--mobile-card .table-cards');
    expect(tableCss).toMatch(/\.table-wrapper--mobile-card\s+\.table-cards\s*\{[^}]*display:\s*block/);

    // Scroll mode: media query should enable horizontal scrolling
    expect(tableCss).toContain('.table-wrapper--mobile-scroll');
    expect(tableCss).toMatch(/\.table-wrapper--mobile-scroll\s*\{[^}]*overflow-x:\s*auto/);

    // Both rules should be inside @media queries for mobile
    expect(tableCss).toMatch(/@media\s*\(\s*max-width:\s*767px\s*\)/);
  });
});
