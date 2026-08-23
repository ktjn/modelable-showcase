import { expect, test } from '@playwright/test'
import vectors from '../parity/runtime-parity.json' with { type: 'json' }

interface VectorSuite {
  version: number
  scenarios: Array<{
    name: string
    steps: Array<{
      name: string
      method: 'GET' | 'POST' | 'PATCH'
      path: string
      body?: unknown
      expect: { category: string, fields: Record<string, unknown> }
    }>
  }>
}

interface Outcome {
  category: string
  body?: unknown
}

const suite = vectors as VectorSuite

test.describe('runtime parity vectors', () => {
  for (const scenario of suite.scenarios) {
    test(scenario.name, async ({ page }) => {
      expect(suite.version).toBe(1)
      const backendRequests: string[] = []
      page.on('request', (request) => {
        if (new URL(request.url()).pathname.startsWith('/api/'))
          backendRequests.push(request.url())
      })
      await page.goto('/')

      const outcomes = await page.evaluate(async (selectedScenario) => {
        const modulePath = '/src/wasm/showcase-runtime.ts'
        const { WasmShowcaseRuntime } = await import(modulePath)
        const runtime = new WasmShowcaseRuntime()
        await runtime.reset()
        const results: Outcome[] = []
        try {
          for (const step of selectedScenario.steps) {
            try {
              const body = await runtime.request({
                method: step.method,
                path: step.path,
                ...(step.body === undefined ? {} : { body: step.body }),
              })
              results.push({ category: 'ok', body })
            }
            catch (error) {
              const status = (error as { status?: number }).status
              results.push({ category: status === 409 ? 'conflict' : status === 404 ? 'not_found' : 'bad_request' })
            }
          }
        }
        finally {
          runtime.terminate()
        }
        return results
      }, scenario)

      expect(backendRequests).toEqual([])
      for (const [index, step] of scenario.steps.entries()) {
        const outcome = outcomes[index]!
        expect(outcome.category, step.name).toBe(step.expect.category)
        if (step.expect.category !== 'ok')
          continue
        for (const [pointer, expected] of Object.entries(step.expect.fields))
          expect(jsonPointer(outcome.body, pointer), `${step.name}: ${pointer}`).toEqual(expected)
      }
    })
  }
})

function jsonPointer(value: unknown, pointer: string): unknown {
  return pointer
    .split('/')
    .slice(1)
    .map(part => part.replaceAll('~1', '/').replaceAll('~0', '~'))
    .reduce<unknown>((current, part) => {
      if (typeof current !== 'object' || current === null)
        return undefined
      return (current as Record<string, unknown>)[part]
    }, value)
}
