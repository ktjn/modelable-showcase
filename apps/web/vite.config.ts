/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Direct consumption of generated/typescript (SPEC.md Sec 4.1/9.1,
      // IMPLEMENTATION_PLAN.md Task 6.1) - no generated files are copied or
      // committed. Kept in sync with tsconfig.app.json's "paths" entry.
      '@generated': fileURLToPath(new URL('../../generated/typescript', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
