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
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
