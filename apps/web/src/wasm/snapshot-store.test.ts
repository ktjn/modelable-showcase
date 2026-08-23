import { IDBFactory } from 'fake-indexeddb'
import { describe, expect, it, vi } from 'vitest'
import type { SnapshotEnvelope, WorkerRequest, WorkerResponse } from './protocol'
import { PersistentWorkerSession, StoredSnapshotError } from './persistent-session'
import { ClinicSnapshotStore } from './snapshot-store'

function snapshot(schemaIdentity = 'clinic-v1'): SnapshotEnvelope {
  return {
    formatVersion: 1,
    modelableVersion: '1.10.1',
    schemaIdentity,
    state: { patients: [] },
  }
}

function success(id: string, persisted?: SnapshotEnvelope): WorkerResponse {
  return {
    id,
    ok: true,
    result: { ready: true },
    ...(persisted === undefined ? {} : { snapshot: persisted }),
  }
}

describe('ClinicSnapshotStore', () => {
  it('starts empty, survives a new store instance, and clears clinic-state', async () => {
    const factory = new IDBFactory()
    const first = new ClinicSnapshotStore(factory, 'persistence-test')
    expect(await first.load()).toBeUndefined()

    await first.save(snapshot())
    await first.close()

    const reloaded = new ClinicSnapshotStore(factory, 'persistence-test')
    expect(await reloaded.load()).toEqual(snapshot())
    await reloaded.clear()
    expect(await reloaded.load()).toBeUndefined()
  })
})

describe('PersistentWorkerSession', () => {
  it('initializes empty on first visit and restores the stored snapshot on reload', async () => {
    const store = new ClinicSnapshotStore(new IDBFactory(), 'restore-test')
    const requestWorker = vi.fn<(request: WorkerRequest) => Promise<WorkerResponse>>()
      .mockImplementation(async request => success(request.id))
    const first = new PersistentWorkerSession(requestWorker, store)

    await first.initialize('first')
    expect(requestWorker).toHaveBeenLastCalledWith({ id: 'first', operation: 'initialize' })

    await store.save(snapshot())
    const reloaded = new PersistentWorkerSession(requestWorker, store)
    await reloaded.initialize('reload')
    expect(requestWorker).toHaveBeenLastCalledWith({
      id: 'reload',
      operation: 'initialize',
      snapshot: snapshot(),
    })
  })

  it('seeds deterministic sample data only on the first static visit', async () => {
    const store = new ClinicSnapshotStore(new IDBFactory(), 'first-visit-seed-test')
    const seeded = snapshot('seeded-schema')
    const requestWorker = vi.fn(async (request: WorkerRequest) => (
      request.operation === 'seed' ? success(request.id, seeded) : success(request.id)
    ))
    const first = new PersistentWorkerSession(requestWorker, store)

    await first.initialize('initialize', 'seed')
    expect(requestWorker.mock.calls.map(([request]) => request.operation)).toEqual(['initialize', 'seed'])
    expect(await store.load()).toEqual(seeded)

    requestWorker.mockClear()
    const reloaded = new PersistentWorkerSession(requestWorker, store)
    await reloaded.initialize('reload', 'do-not-seed')
    expect(requestWorker).toHaveBeenCalledOnce()
    expect(requestWorker).toHaveBeenCalledWith({ id: 'reload', operation: 'initialize', snapshot: seeded })
  })

  it.each(['execute', 'seed'] as const)('persists snapshots after successful %s', async (operation) => {
    const store = new ClinicSnapshotStore(new IDBFactory(), `${operation}-test`)
    const nextSnapshot = snapshot(`${operation}-schema`)
    const requestWorker = vi.fn(async (request: WorkerRequest) => success(request.id, nextSnapshot))
    const session = new PersistentWorkerSession(requestWorker, store)

    await session.request({ id: operation, operation, payload: { type: 'example' } })

    expect(await store.load()).toEqual(nextSnapshot)
  })

  it('does not persist failed mutations or read-only queries', async () => {
    const save = vi.fn()
    const store = { load: vi.fn(), save, clear: vi.fn() }
    const responses: WorkerResponse[] = [
      { id: 'failed', ok: false, error: { category: 'validation', message: 'rejected' } },
      success('query'),
    ]
    const session = new PersistentWorkerSession(async () => responses.shift()!, store)

    await session.request({ id: 'failed', operation: 'execute', payload: {} })
    await session.request({ id: 'query', operation: 'query', payload: {} })

    expect(save).not.toHaveBeenCalled()
  })

  it('persists empty state after reset so an intentional reset stays empty', async () => {
    const store = new ClinicSnapshotStore(new IDBFactory(), 'reset-test')
    await store.save(snapshot())
    const session = new PersistentWorkerSession(async request => success(request.id, snapshot()), store)

    await session.request({ id: 'reset', operation: 'reset' })

    expect(await store.load()).toEqual(snapshot())
  })

  it('turns corrupt and incompatible stored state into an explicit reset path', async () => {
    const corruptStore = {
      load: vi.fn(async () => 'not a snapshot'),
      save: vi.fn(),
      clear: vi.fn(),
    }
    const requestWorker = vi.fn(async (request: WorkerRequest): Promise<WorkerResponse> => (
      request.operation === 'initialize'
        ? { id: request.id, ok: false, error: { category: 'validation', message: 'schema changed' } }
        : success(request.id, snapshot())
    ))

    const corrupt = new PersistentWorkerSession(requestWorker, corruptStore)
    await expect(corrupt.initialize('corrupt')).rejects.toThrow(StoredSnapshotError)
    expect(requestWorker).not.toHaveBeenCalled()

    const incompatibleStore = {
      ...corruptStore,
      load: vi.fn(async () => snapshot('old-schema')),
    }
    const incompatible = new PersistentWorkerSession(requestWorker, incompatibleStore)
    await expect(incompatible.initialize('incompatible')).rejects.toThrow(/reset the sandbox/)

    await incompatible.recoverByReset('recover')
    expect(incompatibleStore.save).toHaveBeenCalledWith(snapshot())
    expect(incompatibleStore.clear).not.toHaveBeenCalled()
  })
})
