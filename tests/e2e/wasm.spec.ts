import { expect, test } from '@playwright/test'
import { bookAppointment, createPatient, runFullClinicJourney, uniqueRunId } from './clinic-journey'

test.describe('Rust WASM clinic runtime', () => {
  test('runs the complete clinic journey and restores it after reload', async ({ page }) => {
    const backendRequests: string[] = []
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/api/'))
        backendRequests.push(request.url())
    })
    await runFullClinicJourney(page)
    expect(backendRequests).toEqual([])
  })

  test('supports patient search and preserves appointment conflict behavior', async ({ page }) => {
    const runId = uniqueRunId()
    const legalName = `Wasm Patient ${runId}`

    await page.goto('/')
    const { patientId } = await createPatient(page, legalName, `wasm.${runId}@example.com`)
    await page.getByRole('link', { name: 'Patients', exact: true }).click()
    await page.getByLabel('Name').fill(legalName)
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByRole('link', { name: legalName })).toBeVisible()

    await page.goto('/schedule')
    await bookAppointment(page, patientId)
    await page.getByLabel('Patient ID').fill(patientId)
    await page.getByLabel('Practitioner ID', { exact: true }).fill(
      'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1',
    )
    await page.getByRole('button', { name: 'Book appointment' }).click()
    await expect(page.getByRole('alert')).toContainText('overlap')
  })

  test('manages a local snapshot through the visible sandbox controls', async ({ page }) => {
    await page.goto('/')
    const identity = page.getByRole('complementary', { name: 'Runtime identity' })
    await expect(identity).toContainText('Rust / WebAssembly')
    await expect(identity).toContainText('1.13.0')
    await expect(identity).toContainText('IndexedDB')

    await page.getByRole('button', { name: 'Seed demo data' }).click()
    await expect(page.getByRole('status')).toContainText('Synthetic demo data loaded')
    await page.getByRole('link', { name: 'Analytics', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
    await expect(page.getByText('125.00', { exact: true })).toBeVisible()

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export snapshot' }).click()
    const download = await downloadPromise
    const snapshotPath = await download.path()
    expect(snapshotPath).toBeTruthy()

    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: 'Reset sandbox' }).click()
    await expect(page.getByRole('status')).toContainText('Browser sandbox reset')
    await page.reload()
    await page.getByRole('link', { name: 'Analytics', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible()
    await expect(page.getByText('0.00', { exact: true }).first()).toBeVisible()

    await page.getByLabel('Import snapshot file').setInputFiles(snapshotPath!)
    await expect(page.getByRole('status')).toContainText('Snapshot imported')
    await expect(page.getByText('125.00', { exact: true })).toBeVisible()
  })
})
