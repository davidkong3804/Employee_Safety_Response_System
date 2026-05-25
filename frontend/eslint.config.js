// ESLint 9 flat config. Kept intentionally lenient — catches real bugs
// (undefined references, unused imports/vars) without nitpicking style.
// Formatting concerns belong to Prettier (.prettierrc.json).
//
// Locally:    npx eslint src/
// CI:         see .github/workflows/ci.yml `lint` job
//
// The tools (eslint, typescript-eslint, @eslint/js) are intentionally
// NOT added to package.json devDependencies so CI does not need to
// regenerate pnpm-lock.yaml. CI installs them on demand.

import js from '@eslint/js'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'coverage/**',
      'node_modules/**',
      '**/*.d.ts',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        // Browser
        window: 'readonly',
        document: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        fetch: 'readonly',
        console: 'readonly',
        URLSearchParams: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        // Vitest / Jest test globals
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        beforeAll: 'readonly',
        afterEach: 'readonly',
        afterAll: 'readonly',
      },
    },
    rules: {
      // Catch real bugs but allow underscore-prefixed unused args.
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // The codebase pragmatically uses `any` in a few mock/type-guard spots.
      // Promote to 'warn' or 'error' once those are eliminated.
      '@typescript-eslint/no-explicit-any': 'off',
      // Empty catch is acceptable for fire-and-forget error suppression.
      'no-empty': ['warn', { allowEmptyCatch: true }],
    },
  },
)
