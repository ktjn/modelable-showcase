import { expect, type Page } from '@playwright/test'

export function uniqueRunId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function createPatient(page: Page, legalName: string, email: string) {
  await page.getByRole('link', { name: 'Patients', exact: true }).click()
  await page.getByRole('link', { name: 'New patient' }).click()
  await page.getByLabel('Legal name').fill(legalName)
  await page.getByLabel('Date of birth').fill('1990-01-01')
  await page.getByLabel('Email').fill(email)
  await page.getByRole('button', { name: 'Create patient' }).click()
  await expect(page.getByRole('heading', { name: legalName })).toBeVisible()

  const patientUrl = page.url()
  const patientId = patientUrl.split('/patients/')[1]
  if (!patientId)
    throw new Error(`patient detail URL did not contain an id: ${patientUrl}`)
  return { patientId, patientUrl }
}

export async function bookAppointment(
  page: Page,
  patientId: string,
  practitionerId = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1',
) {
  await page.getByLabel('Patient ID').fill(patientId)
  await page.getByLabel('Practitioner ID', { exact: true }).fill(practitionerId)
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const row = page.locator('li', { hasText: `patient ${patientId}` })
  await expect(row).toBeVisible()
  return row
}

export async function runFullClinicJourney(page: Page) {
  const runId = uniqueRunId()
  const legalName = `Ada Example ${runId}`

  await page.goto('/')
  const { patientId, patientUrl } = await createPatient(
    page,
    legalName,
    `ada.${runId}@example.com`,
  )

  await page.goto('/schedule')
  const row = await bookAppointment(page, patientId)

  await row.getByRole('button', { name: 'Reschedule' }).click()
  await row.getByRole('button', { name: 'Save' }).click()

  await row.getByRole('button', { name: 'Start encounter' }).click()
  await expect(row.getByText('Encounter in progress.')).toBeVisible()

  await row.getByLabel('Temperature (°C)').fill('37.1')
  await row.getByRole('button', { name: 'Add observation' }).click()
  await row.getByLabel('Vital sign').selectOption('blood_pressure')
  await row.getByRole('button', { name: 'Add observation' }).click()

  await row.getByRole('button', { name: 'Complete encounter' }).click()
  await expect(row.getByText('Encounter completed.')).toBeVisible()

  await page.goto(patientUrl)
  await page.getByLabel('Amount').fill('100.00')
  await page.getByLabel('Tax').fill('25.00')
  await page.getByRole('button', { name: 'Create invoice' }).click()
  const invoiceItem = page.locator('li', { hasText: 'Invoice' })
  await expect(invoiceItem).toBeVisible()

  await invoiceItem.getByRole('button', { name: 'Record payment' }).click()
  await expect(invoiceItem.getByText(/Payment recorded/)).toBeVisible()

  await page.reload()
  await expect(page.getByText('125.00').first()).toBeVisible()

  await page.goto('/schedule')
  await expect(page.locator('li', { hasText: `patient ${patientId}` }).getByText(/status requested/)).toBeVisible()

  await page.goto('/analytics')
  await expect(page.getByText('125.00').first()).toBeVisible()

  return { legalName, patientId, patientUrl }
}
