import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import type { RuntimeInfo, ShowcaseRuntime } from '../api/runtime'
import { runtime as configuredRuntime } from '../api/client'
import { MAX_SNAPSHOT_BYTES } from '../wasm/protocol'
import type { SnapshotEnvelope } from '../wasm/protocol'

interface SandboxRuntime extends ShowcaseRuntime {
  readonly kind: 'wasm'
  seed(): Promise<unknown>
  reset(): Promise<unknown>
  snapshot(): Promise<SnapshotEnvelope>
  restore(snapshot: unknown): Promise<void>
}

function isSandboxRuntime(runtime: ShowcaseRuntime): runtime is SandboxRuntime {
  return runtime.kind === 'wasm'
    && 'seed' in runtime
    && 'reset' in runtime
    && 'snapshot' in runtime
    && 'restore' in runtime
}

function shortSchema(identity: string): string {
  const contracts = identity.split('|')
  const signature = identity.match(/[0-9a-f]{16,}/i)?.[0]
  return `${contracts.length} contracts · ${signature?.slice(0, 8) ?? identity.slice(0, 12)}`
}

export function RuntimePanel({ runtime = configuredRuntime }: { runtime?: ShowcaseRuntime }) {
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string>()
  const [error, setError] = useState<string>()
  const info = useQuery({
    queryKey: ['runtime-info', runtime.kind],
    queryFn: () => runtime.info(),
    staleTime: Infinity,
  })

  async function mutate(label: string, action: () => Promise<unknown>) {
    setBusy(true)
    setError(undefined)
    setMessage(undefined)
    try {
      await action()
      await queryClient.invalidateQueries({ predicate: query => query.queryKey[0] !== 'runtime-info' })
      setMessage(label)
    }
    catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
    finally {
      setBusy(false)
    }
  }

  async function exportSnapshot(runtime: SandboxRuntime) {
    await mutate('Snapshot exported.', async () => {
      const snapshot = await runtime.snapshot()
      const url = URL.createObjectURL(new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a')
      link.href = url
      link.download = 'modelable-clinic-snapshot.json'
      link.click()
      URL.revokeObjectURL(url)
    })
  }

  async function importSnapshot(event: ChangeEvent<HTMLInputElement>, runtime: SandboxRuntime) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file)
      return
    if (file.size > MAX_SNAPSHOT_BYTES) {
      setError('The selected clinic snapshot exceeds the 2 MiB limit')
      return
    }
    await mutate('Snapshot imported into this browser.', async () => {
      await runtime.restore(JSON.parse(await file.text()) as unknown)
    })
  }

  const identity = info.data as RuntimeInfo | undefined
  const sandbox = isSandboxRuntime(runtime) ? runtime : undefined

  return (
    <aside className="runtime-panel" aria-label="Runtime identity">
      <div className="runtime-panel__identity">
        <span className="runtime-panel__pulse" aria-hidden="true" />
        {identity
          ? (
              <dl>
                <div><dt>Runtime</dt><dd>{identity.runtime}</dd></div>
                <div><dt>Modelable</dt><dd>{identity.modelableVersion}</dd></div>
                <div><dt>Schema</dt><dd title={identity.schemaIdentity}>{shortSchema(identity.schemaIdentity)}</dd></div>
                <div><dt>Storage</dt><dd>{identity.storage}</dd></div>
              </dl>
            )
          : <span className="runtime-panel__loading">Reading runtime identity…</span>}
      </div>
      {info.error && <span className="runtime-panel__error" role="alert">Runtime identity unavailable.</span>}
      {sandbox && (
        <div className="runtime-panel__sandbox">
          <div className="runtime-panel__controls" aria-label="Browser sandbox controls">
            <button disabled={busy} onClick={() => void mutate('Synthetic demo data loaded.', () => sandbox.seed())}>Seed demo data</button>
            <button disabled={busy} onClick={() => {
              if (window.confirm('Reset all clinic data stored by this browser?'))
                void mutate('Browser sandbox reset.', () => sandbox.reset())
            }}>Reset sandbox</button>
            <button disabled={busy} onClick={() => void exportSnapshot(sandbox)}>Export snapshot</button>
            <button disabled={busy} onClick={() => fileInput.current?.click()}>Import snapshot</button>
            <input
              ref={fileInput}
              className="runtime-panel__file"
              type="file"
              accept="application/json,.json"
              aria-label="Import snapshot file"
              onChange={event => void importSnapshot(event, sandbox)}
            />
          </div>
          <span className="runtime-panel__warning">Synthetic demo only · browser-local storage · do not enter real patient data.</span>
          {message && <span className="runtime-panel__status" role="status">{message}</span>}
          {error && <span className="runtime-panel__error" role="alert">{error}</span>}
        </div>
      )}
    </aside>
  )
}
