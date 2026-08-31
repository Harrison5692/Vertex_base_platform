import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

export default [
  { ignores: ['dist'] },
  {
    files: ['vite.config.js'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['**/*.{js,jsx}'],
    ignores: ['vite.config.js'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'no-unused-vars': ['warn', { varsIgnorePattern: '^[A-Z_]' }],
      // Downgraded to warn, not disabled: this rule correctly flags a
      // real category of bug (setState synchronously during an effect
      // can cascade re-renders), but the standard "fetch data on mount"
      // pattern (useEffect(load, [])) trips it too, and that pattern is
      // correct and used throughout this codebase. Worth seeing, not
      // worth blocking a build over.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
]
