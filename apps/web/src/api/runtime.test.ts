import { describe, expect, it, vi } from 'vitest'
import type { SnapshotStore } from '../wasm/persistent-session'
import type { SnapshotEnvelope, WorkerRequest, WorkerResponse } from '../wasm/protocol'
import { WasmShowcaseRuntime } from '../wasm/showcase-runtime'
import { createShowcaseClient } from './client'
import { ApiError, HttpRuntime } from './runtime'

const SNAPSHOT: SnapshotEnvelope = {
  formatVersion: 1,
  modelableVersion: '1.10.1',
  schemaIdentity: 'clinic-v1',
  state: { patients: [] },
}

class RespondingWorker {
  readonly requests: WorkerRequest[] = []
  readonly #listeners = new Map<string, Array<(event: MessageEvent<unknown>) => void>>()
  readonly #respond: (request: WorkerRequest) => WorkerResponse

  constructor(respond: (request: WorkerRequest) => WorkerResponse) {
    this.#respond = respond
  }

  addEventListener(type: string, listener: (event: MessageEvent<unknown>) => void): void {
    const listeners = this.#listeners.get(type) ?? []
    listeners.push(listener)
    this.#listeners.set(type, listeners)
  }

  postMessage(request: WorkerRequest): void {
    this.requests.push(request)
    queueMicrotask(() => {
      const event = new MessageEvent('message', { data: this.#respond(request) })
      for (const listener of this.#listeners.get('message') ?? [])
        listener(event)
    })
  }

  terminate(): void {}
}

function memoryStore(initial?: SnapshotEnvelope): SnapshotStore & { saved: SnapshotEnvelope[] } {
  let value = initial
  const saved: SnapshotEnvelope[] = []
  return {
    saved,
    load: async () => value,
    save: async (snapshot) => {
      value = snapshot
      saved.push(snapshot)
    },
    clear: async () => {
      value = undefined
    },
  }
}

describe('runtime-neutral showcase client', () => {
  it('keeps the same GET/POST/PATCH request contract for an HTTP runtime', async () => {
    const fetchMock = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => (
      new Response(JSON.stringify({ method: init?.method, body: init?.body ?? null }))
    ))
    const client = createShowcaseClient(new HttpRuntime('/root', fetchMock))

    await expect(client.get('/api/patients')).resolves.toEqual({ method: 'GET', body: null })
    await expect(client.post('/api/patients', { id: 'p-1' })).resolves.toEqual({
      method: 'POST',
      body: '{"id":"p-1"}',
    })
    await expect(client.patch('/api/patients/p-1', { name: 'Ada' })).resolves.toEqual({
      method: 'PATCH',
      body: '{"name":"Ada"}',
    })
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
      '/root/api/patients',
      '/root/api/patients',
      '/root/api/patients/p-1',
    ])
  })

  it('routes the same client contract only through one initialized worker', async () => {
    const store = memoryStore(SNAPSHOT)
    const worker = new RespondingWorker(request => (
      request.operation === 'initialize'
        ? { id: request.id, ok: true, result: { ready: true } }
        : {
            id: request.id,
            ok: true,
            result: request.payload,
            ...(request.operation === 'execute' ? { snapshot: SNAPSHOT } : {}),
          }
    ))
    let id = 0
    const runtime = new WasmShowcaseRuntime(
      () => worker as unknown as Worker,
      store,
      () => `request-${++id}`,
    )
    const client = createShowcaseClient(runtime)

    await expect(client.get('/api/patients')).resolves.toEqual({
      method: 'GET',
      path: '/api/patients',
    })
    await expect(client.post('/api/patients', { id: 'p-1' })).resolves.toEqual({
      method: 'POST',
      path: '/api/patients',
      body: { id: 'p-1' },
    })
    await expect(client.patch('/api/patients/p-1', { name: 'Ada' })).resolves.toEqual({
      method: 'PATCH',
      path: '/api/patients/p-1',
      body: { name: 'Ada' },
    })

    expect(worker.requests).toEqual([
      { id: 'request-1', operation: 'initialize', snapshot: SNAPSHOT },
      {
        id: 'request-2',
        operation: 'query',
        payload: { method: 'GET', path: '/api/patients' },
      },
      {
        id: 'request-3',
        operation: 'execute',
        payload: { method: 'POST', path: '/api/patients', body: { id: 'p-1' } },
      },
      {
        id: 'request-4',
        operation: 'execute',
        payload: { method: 'PATCH', path: '/api/patients/p-1', body: { name: 'Ada' } },
      },
    ])
    expect(store.saved).toEqual([SNAPSHOT, SNAPSHOT])
    runtime.terminate()
  })

  it('normalizes worker errors to the existing ApiError behavior', async () => {
    const worker = new RespondingWorker(request => (
      request.operation === 'initialize'
        ? { id: request.id, ok: true, result: {} }
        : { id: request.id, ok: false, error: { category: 'conflict', message: 'already exists' } }
    ))
    const runtime = new WasmShowcaseRuntime(
      () => worker as unknown as Worker,
      memoryStore(),
      () => crypto.randomUUID(),
    )

    await expect(runtime.request({ method: 'POST', path: '/api/patients', body: {} }))
      .rejects.toEqual(new ApiError(409, { error: 'already exists', category: 'conflict' }))
    runtime.terminate()
  })
})
