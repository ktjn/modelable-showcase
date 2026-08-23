import { describe, expect, it, vi } from 'vitest'
import type { WorkerRequest } from './protocol'
import { WorkerRuntimeHost, type WasmRuntime } from './worker-runtime'

function ok(result: unknown): string {
  return JSON.stringify({ ok: true, result })
}

function fakeRuntime(): WasmRuntime {
  return {
    initialize: vi.fn(() => ok({ counts: { patients: 0 } })),
    execute: vi.fn(() => ok({ patientId: 'patient-1' })),
    query: vi.fn(() => ok([{ patientId: 'patient-1' }])),
    snapshot: vi.fn(() => ok({ formatVersion: 1, state: {} })),
    reset: vi.fn(() => ok({ counts: { patients: 0 } })),
    seed: vi.fn(() => ok({ counts: { patients: 1 } })),
  }
}

describe('WorkerRuntimeHost', () => {
  it('loads WASM once and preserves IDs across multiple queued requests', async () => {
    const runtime = fakeRuntime()
    const loader = vi.fn(async () => runtime)
    const host = new WorkerRuntimeHost(loader)

    const responses = await Promise.all([
      host.handle({ id: 'initialize-1', operation: 'initialize' }),
      host.handle({ id: 'query-2', operation: 'query', payload: { type: 'Analytics' } }),
    ])

    expect(loader).toHaveBeenCalledTimes(1)
    expect(responses.map(response => response.id)).toEqual(['initialize-1', 'query-2'])
    expect(runtime.initialize).toHaveBeenCalledWith(undefined)
    expect(runtime.query).toHaveBeenCalledWith(JSON.stringify({ type: 'Analytics' }))
  })

  it('passes a supplied snapshot to initialization', async () => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(async () => runtime)
    const snapshot = { formatVersion: 1, state: { patients: {} } }

    const response = await host.handle({ id: 'restore', operation: 'initialize', snapshot })

    expect(response.ok).toBe(true)
    expect(runtime.initialize).toHaveBeenCalledWith(JSON.stringify(snapshot))
  })

  it('injects time and snapshots only after a successful mutation', async () => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(async () => runtime, () => '2026-09-01T08:00:00.000Z')

    const response = await host.handle({
      id: 'create',
      operation: 'execute',
      payload: { type: 'CreatePatient', payload: { patientId: 'patient-1' } },
    })

    expect(runtime.execute).toHaveBeenCalledWith(JSON.stringify({
      type: 'CreatePatient',
      payload: { patientId: 'patient-1' },
      now: '2026-09-01T08:00:00.000Z',
    }))
    expect(runtime.snapshot).toHaveBeenCalledTimes(1)
    expect(response).toEqual({
      id: 'create',
      ok: true,
      result: { patientId: 'patient-1' },
      snapshot: { formatVersion: 1, state: {} },
    })

    await host.handle({ id: 'query', operation: 'query', payload: { type: 'Analytics' } })
    expect(runtime.snapshot).toHaveBeenCalledTimes(1)
  })

  it('dispatches route-like requests into the tagged Rust command and query ABI', async () => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(
      async () => runtime,
      () => '2026-09-01T08:00:00.000Z',
      () => 'observation-1',
    )

    await host.handle({
      id: 'observation',
      operation: 'execute',
      payload: {
        method: 'POST',
        path: '/api/encounters/encounter-1/observations',
        body: { code: 'pulse' },
      },
    })
    await host.handle({
      id: 'schedule',
      operation: 'query',
      payload: {
        method: 'GET',
        path: '/api/schedule?date=2026-09-01&practitioner=practitioner-1',
      },
    })

    expect(runtime.execute).toHaveBeenCalledWith(JSON.stringify({
      type: 'RecordObservation',
      payload: {
        code: 'pulse',
        observationId: 'observation-1',
        encounterId: 'encounter-1',
        isAbnormal: false,
        recordedAt: '2026-09-01T08:00:00.000Z',
      },
      now: '2026-09-01T08:00:00.000Z',
    }))
    expect(runtime.query).toHaveBeenCalledWith(JSON.stringify({
      type: 'DailySchedule',
      payload: { date: '2026-09-01', practitionerId: 'practitioner-1' },
    }))
  })

  it('rejects unsupported and mismatched route requests as bad requests', async () => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(async () => runtime)

    const unsupported = await host.handle({
      id: 'unsupported',
      operation: 'query',
      payload: { method: 'GET', path: '/api/unknown' },
    })
    const mismatched = await host.handle({
      id: 'mismatched',
      operation: 'execute',
      payload: { method: 'GET', path: '/api/patients' },
    })

    expect(unsupported).toEqual({
      id: 'unsupported',
      ok: false,
      error: { category: 'bad_request', message: 'unsupported showcase route GET /api/unknown' },
    })
    expect(mismatched).toEqual({
      id: 'mismatched',
      ok: false,
      error: { category: 'bad_request', message: 'GET routes must use the query worker operation' },
    })
    expect(runtime.query).not.toHaveBeenCalled()
    expect(runtime.execute).not.toHaveBeenCalled()
  })

  it.each(['reset', 'seed'] as const)('snapshots after %s', async (operation) => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(async () => runtime)

    const response = await host.handle({ id: operation, operation })

    expect(response.ok).toBe(true)
    expect(runtime.snapshot).toHaveBeenCalledTimes(1)
    expect(response).toHaveProperty('snapshot')
  })

  it('validates and restores a snapshot through the Rust boundary', async () => {
    const runtime = fakeRuntime()
    const host = new WorkerRuntimeHost(async () => runtime)
    const snapshot = {
      formatVersion: 1,
      modelableVersion: '1.10.1',
      schemaIdentity: 'clinic-v1',
      state: { patients: {} },
    }

    const invalid = await host.handle({ id: 'invalid', operation: 'restore', snapshot: { state: {} } })
    const restored = await host.handle({ id: 'restore', operation: 'restore', snapshot })

    expect(invalid).toEqual({
      id: 'invalid',
      ok: false,
      error: { category: 'bad_request', message: 'invalid clinic snapshot envelope' },
    })
    expect(runtime.initialize).toHaveBeenCalledWith(JSON.stringify(snapshot))
    expect(runtime.snapshot).toHaveBeenCalledTimes(1)
    expect(restored).toHaveProperty('snapshot')
  })

  it('does not snapshot a rejected mutation', async () => {
    const runtime = fakeRuntime()
    vi.mocked(runtime.execute).mockReturnValue(JSON.stringify({
      ok: false,
      error: { category: 'conflict', message: 'patient already exists' },
    }))
    const host = new WorkerRuntimeHost(async () => runtime)

    const response = await host.handle({ id: 'duplicate', operation: 'execute', payload: {} })

    expect(response).toEqual({
      id: 'duplicate',
      ok: false,
      error: { category: 'conflict', message: 'patient already exists' },
    })
    expect(runtime.snapshot).not.toHaveBeenCalled()
  })

  it('turns startup failures into actionable responses instead of hanging', async () => {
    const host = new WorkerRuntimeHost(async () => {
      throw new Error('asset returned 404')
    })

    const response = await host.handle({ id: 'startup', operation: 'initialize' })

    expect(response).toEqual({
      id: 'startup',
      ok: false,
      error: {
        category: 'internal',
        message: expect.stringContaining('Run `make wasm-build` and reload'),
      },
    })
  })

  it('rejects unknown operations without dropping the request ID', async () => {
    const runtime = fakeRuntime()
    const loader = vi.fn(async () => runtime)
    const host = new WorkerRuntimeHost(loader)
    const request = { id: 'unknown', operation: 'explode' } as unknown as WorkerRequest

    const response = await host.handle(request)

    expect(response).toEqual({
      id: 'unknown',
      ok: false,
      error: { category: 'bad_request', message: "unknown worker operation 'explode'" },
    })
    expect(loader).not.toHaveBeenCalled()
  })
})
