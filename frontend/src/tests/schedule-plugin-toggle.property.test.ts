/**
 * Property 27: Plugin toggle state reflects effective config
 *
 * For any combination of global plugin config and site-level plugin_config,
 * the ScheduleTab toggle switches shall display the effective enabled/disabled
 * state for each plugin. When plugin_config is NULL, all toggles shall reflect
 * the global default state.
 *
 * **Validates: Requirements 24a.3, 24a.4, 24a.6**
 */
import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { computeEffectivePluginStates } from '../components/hierarchy/tabs/ScheduleTab';

const ALL_PLUGIN_NAMES = [
  'LocalePlugin',
  'PreCaptureScriptPlugin',
  'ModalDismissPlugin',
  'StructuredDataPlugin',
  'ShopifyPlugin',
  'HTMLParserPlugin',
  'OCRPlugin',
  'ContractComparisonPlugin',
  'EvidencePreservationPlugin',
  'DBStoragePlugin',
  'ObjectStoragePlugin',
  'AlertPlugin',
];

interface PluginInfo {
  name: string;
  label: string;
  defaultEnabled: boolean;
}

const pluginInfoArb: fc.Arbitrary<PluginInfo[]> = fc.constant(
  ALL_PLUGIN_NAMES.map((name) => ({
    name,
    label: `${name} description`,
    defaultEnabled: true,
  })),
);

const pluginConfigArb: fc.Arbitrary<Record<string, unknown> | null> = fc.oneof(
  fc.constant(null),
  fc.record({
    disabled: fc.subarray(ALL_PLUGIN_NAMES, { minLength: 0, maxLength: 6 }),
    enabled: fc.subarray(ALL_PLUGIN_NAMES, { minLength: 0, maxLength: 6 }),
    params: fc.constant({}),
  }),
);

describe('Property 27: Plugin toggle state reflects effective config', () => {
  it('when plugin_config is NULL, all toggles reflect global default state', () => {
    fc.assert(
      fc.property(pluginInfoArb, (plugins) => {
        const states = computeEffectivePluginStates(plugins, null);

        for (const plugin of plugins) {
          expect(states[plugin.name]).toBe(plugin.defaultEnabled);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('disabled plugins in site config are toggled off', () => {
    fc.assert(
      fc.property(
        pluginInfoArb,
        fc.subarray(ALL_PLUGIN_NAMES, { minLength: 1, maxLength: 6 }),
        (plugins, disabled) => {
          const config = { disabled, enabled: [], params: {} };
          const states = computeEffectivePluginStates(plugins, config);

          for (const name of disabled) {
            expect(states[name]).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('enabled plugins in site config are toggled on', () => {
    fc.assert(
      fc.property(
        pluginInfoArb,
        fc.subarray(ALL_PLUGIN_NAMES, { minLength: 1, maxLength: 6 }),
        (plugins, enabled) => {
          const config = { disabled: [], enabled, params: {} };
          const states = computeEffectivePluginStates(plugins, config);

          for (const name of enabled) {
            expect(states[name]).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('global + site config combination produces correct toggle state', () => {
    fc.assert(
      fc.property(pluginInfoArb, pluginConfigArb, (plugins, config) => {
        const states = computeEffectivePluginStates(plugins, config);

        // Every plugin must have a state
        for (const plugin of plugins) {
          expect(typeof states[plugin.name]).toBe('boolean');
        }

        if (config === null) {
          // All should match global defaults
          for (const plugin of plugins) {
            expect(states[plugin.name]).toBe(plugin.defaultEnabled);
          }
        } else {
          const disabled = (config.disabled as string[]) || [];
          const enabled = (config.enabled as string[]) || [];

          for (const plugin of plugins) {
            let expected = plugin.defaultEnabled;
            if (disabled.includes(plugin.name)) expected = false;
            if (enabled.includes(plugin.name)) expected = true;
            expect(states[plugin.name]).toBe(expected);
          }
        }
      }),
      { numRuns: 100 },
    );
  });
});
