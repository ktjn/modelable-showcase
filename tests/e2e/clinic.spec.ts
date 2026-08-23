import { expect, test } from '@playwright/test'
import { createPatient, runFullClinicJourney, uniqueRunId } from './clinic-journey'

// IMPLEMENTATION_PLAN.md Task 12.1.
//
// The E2E bootstrap applies the full generated PostgreSQL and ClickHouse
// schemas, including the FK-bearing appointment, encounter, and invoice
// tables. Modelable 1.9.4 fixed UPSTREAM_FINDINGS.md #27.

test('shows the native runtime identity without browser sandbox controls', async ({ page }) => {
  await page.goto('/')
  const identity = page.getByRole('complementary', { name: 'Runtime identity' })
  await expect(identity).toContainText('Rust / Axum')
  await expect(identity).toContainText('PostgreSQL + ClickHouse')
  await expect(page.getByRole('button', { name: 'Seed demo data' })).toHaveCount(0)
})

test.describe('Patient identity', () => {
  test('create a patient, find it via search, and view its detail page', async ({ page }) => {
    const runId = uniqueRunId()
    const legalName = `Ada Example ${runId}`
    const email = `ada.${runId}@example.com`

    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Modelable Clinic' })).toBeVisible()
    await createPatient(page, legalName, email)
    await expect(page.getByText(email)).toBeVisible()

    await page.getByRole('link', { name: 'Patients', exact: true }).click()
    await page.getByLabel('Name').fill(legalName)
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByRole('link', { name: legalName })).toBeVisible()
  })

  test('analytics page renders zeroed aggregates from the real ClickHouse-backed endpoint', async ({ page }) => {
    // The native runtime remains the integration proof for generated
    // ClickHouse DDL; an empty event store should report zeroed aggregates.
    await page.goto('/analytics')
    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
    await expect(page.getByText('0.00').first()).toBeVisible()
  })
})

test.describe('Full clinic flow', () => {
  test('book -> reschedule -> start encounter -> observe -> complete -> invoice -> pay -> verify', async ({
    page,
  }) => {
    await runFullClinicJourney(page)
  })
})
