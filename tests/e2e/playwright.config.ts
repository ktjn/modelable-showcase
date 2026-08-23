import { defineConfig, devices } from '@playwright/test'

// IMPLEMENTATION_PLAN.md Task 12.1. Runs against the docker-compose `web`
// service (nginx, proxying /api to the `api` service - apps/web/nginx.conf),
// so this exercises the same containers Task 11.1 built, not a dev server.
export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      testIgnore: /wasm\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'wasm-chromium',
      testMatch: /wasm\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.E2E_WASM_BASE_URL ?? 'http://127.0.0.1:4174',
      },
    },
  ],
  webServer: {
    command: 'npm --prefix ../../apps/web run dev -- --host 127.0.0.1 --port 4174',
    env: { ...process.env, VITE_SHOWCASE_RUNTIME: 'wasm' },
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
