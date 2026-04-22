import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Allow any in catch blocks and test files — too many legacy usages
      '@typescript-eslint/no-explicit-any': 'warn',
      // Allow unused vars with _ prefix
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],
      // Downgrade react-refresh to warn for re-exported utilities
      'react-refresh/only-export-components': 'warn',
      // Downgrade set-state-in-effect to warn (common pattern for responsive layouts)
      'react-hooks/set-state-in-effect': 'warn',
      // Downgrade purity check to warn (Math.random in useRef is safe)
      'react-hooks/purity': 'warn',
    },
  },
  // Test files: relax rules further
  {
    files: ['**/*.test.{ts,tsx}', '**/__tests__/**/*.{ts,tsx}', '**/tests/**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': 'warn',
    },
  },
])
