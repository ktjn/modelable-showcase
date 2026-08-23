import { expect, test } from '@playwright/test'

test.describe('GitHub Pages static build', () => {
  test('loads every runtime asset under the repository base and survives direct reload', async ({ page }) => {
    const responses = new Map<string, number>()
    const backendRequests: string[] = []
    page.on('response', response => responses.set(response.url(), response.status()))
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/api/'))
        backendRequests.push(request.url())
    })

    await page.goto('./#/schedule')
    await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()
    await expect(page.getByText('Loading schedule…')).toBeHidden()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Schedule' })).toBeVisible()
    await expect(page.getByText('Loading schedule…')).toBeHidden()
    await expect(page.getByRole('alert')).toHaveCount(0)

    expect(new URL(page.url()).pathname).toBe('/modelable-showcase/')
    expect(new URL(page.url()).hash).toBe('#/schedule')
    expect(backendRequests).toEqual([])

    const loaded = [...responses.entries()]
    for (const [, status] of loaded)
      expect(status).toBeLessThan(400)
    expect(loaded.some(([url]) => /\/assets\/runtime\.worker-[^/]+\.js$/.test(url))).toBe(true)
    expect(loaded.some(([url]) => url.endsWith('/wasm/showcase_wasm.js'))).toBe(true)
    expect(loaded.some(([url]) => url.endsWith('/wasm/showcase_wasm_bg.wasm'))).toBe(true)
    expect(loaded.every(([url]) => new URL(url).pathname.startsWith('/modelable-showcase/'))).toBe(true)
  })

  test('identifies and safely resets the browser-local sandbox', async ({ page }) => {
    await page.goto('./')
    const identity = page.getByRole('complementary', { name: 'Runtime identity' })
    await expect(identity).toContainText('Rust / WebAssembly')
    await expect(identity).toContainText('IndexedDB')
    await expect(identity).toContainText('do not enter real patient data')

    await page.getByRole('button', { name: 'Seed demo data' }).click()
    await expect(page.getByRole('status')).toContainText('Synthetic demo data loaded')
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: 'Reset sandbox' }).click()
    await expect(page.getByRole('status')).toContainText('Browser sandbox reset')
  })
})
