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

  test('seed persists useful analytics and reset clears the sandbox', async ({ page }) => {
    await page.goto('/')
    const result = await page.evaluate(async () => {
      const modulePath = '/src/wasm/showcase-runtime.ts'
      const { WasmShowcaseRuntime } = await import(modulePath)
      const seededRuntime = new WasmShowcaseRuntime()
      const seeded = await seededRuntime.seed<{ counts: { patients: number } }>()
      seededRuntime.terminate()

      const restoredRuntime = new WasmShowcaseRuntime()
      const analytics = await restoredRuntime.request<{ billedTotal: string, paidTotal: string }>({
        method: 'GET',
        path: '/api/analytics/clinic',
      })
      await restoredRuntime.reset()
      restoredRuntime.terminate()

      const resetRuntime = new WasmShowcaseRuntime()
      const patients = await resetRuntime.request<unknown[]>({ method: 'GET', path: '/api/patients' })
      resetRuntime.terminate()
      return { seeded, analytics, patients }
    })

    expect(result.seeded.counts.patients).toBeGreaterThan(0)
    expect(result.analytics).toMatchObject({ billedTotal: '125.00', paidTotal: '75.00' })
    expect(result.patients).toEqual([])
  })
})
