import { defineConfig, devices } from '@playwright/test'

const webServer = process.env.E2E_SKIP_WASM_SERVERS === '1'
  ? undefined
  : [
      {
        command: 'npm --prefix ../../apps/web run dev -- --host 127.0.0.1 --port 4174',
        env: { ...process.env, VITE_SHOWCASE_RUNTIME: 'wasm' },
        url: 'http://127.0.0.1:4174',
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      },
      {
        command: 'npm --prefix ../../apps/web run preview -- --host 127.0.0.1 --port 4175',
        env: { ...process.env, VITE_SHOWCASE_RUNTIME: 'wasm', VITE_SHOWCASE_STATIC: 'true' },
        url: 'http://127.0.0.1:4175/modelable-showcase/',
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      },
    ]

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
      testIgnore: /(wasm|pages)\.spec\.ts/,
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
    {
      name: 'pages-chromium',
      testMatch: /pages\.spec\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: process.env.E2E_PAGES_BASE_URL ?? 'http://127.0.0.1:4175/modelable-showcase/',
      },
    },
  ],
  webServer,
})
