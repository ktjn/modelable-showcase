import { expect, test } from '@playwright/test'

// IMPLEMENTATION_PLAN.md Task 12.1.
//
// The E2E bootstrap applies the full generated PostgreSQL and ClickHouse
// schemas, including the FK-bearing appointment, encounter, and invoice
// tables. Modelable 1.9.4 fixed UPSTREAM_FINDINGS.md #27.

function uniqueRunId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

test.describe('Patient identity', () => {
  test('create a patient, find it via search, and view its detail page', async ({ page }) => {
    const runId = uniqueRunId()
    const legalName = `Ada Example ${runId}`

    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Modelable Clinic' })).toBeVisible()

    await page.getByRole('link', { name: 'Patients', exact: true }).click()
    await page.getByRole('link', { name: 'New patient' }).click()

    await page.getByLabel('Legal name').fill(legalName)
    await page.getByLabel('Date of birth').fill('1990-01-01')
    await page.getByLabel('Email').fill(`ada.${runId}@example.com`)
    await page.getByRole('button', { name: 'Create patient' }).click()

    // Successful creation navigates to /patients/:id.
    await expect(page.getByRole('heading', { name: legalName })).toBeVisible()
    await expect(page.getByText(`ada.${runId}@example.com`)).toBeVisible()

    await page.getByRole('link', { name: 'Patients', exact: true }).click()
    await page.getByLabel('Name').fill(legalName)
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByRole('link', { name: legalName })).toBeVisible()
  })

  test('analytics page renders zeroed aggregates from the real ClickHouse-backed endpoint', async ({ page }) => {
    // Unlike Postgres, ClickHouse's generated DDL has no FOREIGN KEY concept
    // and the full set applies cleanly (scripts/setup-full-database.py), so
    // GET /api/analytics/clinic (Task 9.5) works on this schema - it just
    // reports no activity, since nothing writes to it without appointments/
    // invoices/payments.
    await page.goto('/analytics')
    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
    await expect(page.getByText('0.00').first()).toBeVisible()
  })
})

test.describe('Full clinic flow', () => {
  test('book -> reschedule -> start encounter -> observe -> complete -> invoice -> pay -> verify', async ({
    page,
  }) => {
    const runId = uniqueRunId()
    const legalName = `Ada Example ${runId}`

    // 1. open product
    await page.goto('/')

    // 2. create fictional patient
    await page.getByRole('link', { name: 'Patients', exact: true }).click()
    await page.getByRole('link', { name: 'New patient' }).click()
    await page.getByLabel('Legal name').fill(legalName)
    await page.getByLabel('Date of birth').fill('1990-01-01')
    await page.getByLabel('Email').fill(`ada.${runId}@example.com`)
    await page.getByRole('button', { name: 'Create patient' }).click()
    await expect(page.getByRole('heading', { name: legalName })).toBeVisible()
    const patientUrl = page.url()
    const patientId = patientUrl.split('/patients/')[1]

    // 3. book appointment
    await page.goto('/schedule')
    await page.getByLabel('Patient ID').fill(patientId)
    await page.getByLabel('Practitioner ID').fill('a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1')
    await page.getByRole('button', { name: 'Book appointment' }).click()
    const row = page.locator('li', { hasText: `patient ${patientId}` })
    await expect(row).toBeVisible()

    // 4. reschedule appointment
    await row.getByRole('button', { name: 'Reschedule' }).click()
    await row.getByRole('button', { name: 'Save' }).click()

    // 5. start encounter
    await row.getByRole('button', { name: 'Start encounter' }).click()
    await expect(row.getByText('Encounter in progress.')).toBeVisible()

    // 6. add temperature and blood-pressure observations
    await row.getByLabel('Temperature (°C)').fill('37.1')
    await row.getByRole('button', { name: 'Add observation' }).click()
    await row.getByLabel('Vital sign').selectOption('blood_pressure')
    await row.getByRole('button', { name: 'Add observation' }).click()

    // 7. complete encounter
    await row.getByRole('button', { name: 'Complete encounter' }).click()
    await expect(row.getByText('Encounter completed.')).toBeVisible()

    // 8. create invoice
    await page.goto(patientUrl)
    await page.getByLabel('Amount').fill('100.00')
    await page.getByRole('button', { name: 'Create invoice' }).click()
    const invoiceItem = page.locator('li', { hasText: 'Invoice' })
    await expect(invoiceItem).toBeVisible()

    // 9. record payment
    await invoiceItem.getByRole('button', { name: 'Record payment' }).click()
    await expect(invoiceItem.getByText(/Payment recorded/)).toBeVisible()

    // 10. open patient summary and verify clinical + billing data
    await page.reload()
    await expect(page.getByText('125.00')).toBeVisible()

    // 11. open schedule and verify appointment state
    await page.goto('/schedule')
    await expect(page.getByText('completed')).toBeVisible()

    // 12. open analytics and verify aggregate reflects transaction
    await page.goto('/analytics')
    await expect(page.getByText('125.00')).toBeVisible()
  })
})
