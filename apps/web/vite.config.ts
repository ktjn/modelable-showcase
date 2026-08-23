/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: process.env.VITE_SHOWCASE_STATIC === 'true' ? '/modelable-showcase/' : '/',
  plugins: [react()],
  resolve: {
    alias: {
      // Direct consumption of generated/typescript (SPEC.md Sec 4.1/9.1,
      // IMPLEMENTATION_PLAN.md Task 6.1) - no generated files are copied or
      // committed. Kept in sync with tsconfig.app.json's "paths" entry.
      '@generated': fileURLToPath(new URL('../../generated/typescript', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // Dev-only same-origin proxy to apps/api's default SHOWCASE_API_ADDR
      // (Task 10.1). src/api/client.ts defaults VITE_API_BASE_URL to '' so
      // requests are same-origin through this proxy - a browser SPA calling
      // a cross-origin Rust API directly needs CORS middleware apps/api does
      // not have, and this dev server already sits between the two.
      '/api': 'http://127.0.0.1:8080',
      '/openapi.json': 'http://127.0.0.1:8080',
      '/docs': 'http://127.0.0.1:8080',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
