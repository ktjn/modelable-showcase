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
})
