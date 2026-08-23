import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ShowcaseRuntime } from '../api/runtime'
import { RuntimePanel } from './RuntimePanel'

function renderPanel(runtime: ShowcaseRuntime) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RuntimePanel runtime={runtime} />
    </QueryClientProvider>,
  )
}

describe('RuntimePanel', () => {
  it('shows HTTP provenance without local sandbox actions', async () => {
    const runtime: ShowcaseRuntime = {
      kind: 'http',
      request: vi.fn(),
      info: vi.fn().mockResolvedValue({
        runtime: 'Rust / Axum',
        modelableVersion: '1.10.1',
        schemaIdentity: 'patient.PatientDb@v2:1234567890abcdef',
        storage: 'PostgreSQL + ClickHouse',
      }),
    }

    renderPanel(runtime)

    expect(await screen.findByText('Rust / Axum')).toBeInTheDocument()
    expect(screen.getByText('1 contracts · 12345678')).toHaveAttribute(
      'title',
      'patient.PatientDb@v2:1234567890abcdef',
    )
    expect(screen.queryByRole('button', { name: 'Seed demo data' })).not.toBeInTheDocument()
  })

  it('runs visible browser controls and keeps the clinical-data warning present', async () => {
    const runtime = {
      kind: 'wasm' as const,
      request: vi.fn(),
      info: vi.fn().mockResolvedValue({
        runtime: 'Rust / WebAssembly',
        modelableVersion: '1.10.1',
        schemaIdentity: 'clinic@v1:1234567890abcdef',
        storage: 'IndexedDB',
      }),
      seed: vi.fn().mockResolvedValue({}),
      reset: vi.fn().mockResolvedValue({}),
      snapshot: vi.fn(),
      restore: vi.fn(),
    }
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderPanel(runtime)

    await screen.findByText('Rust / WebAssembly')
    expect(screen.getByText(/do not enter real patient data/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Seed demo data' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Synthetic demo data loaded')
    await user.click(screen.getByRole('button', { name: 'Reset sandbox' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Browser sandbox reset')
    expect(runtime.seed).toHaveBeenCalledTimes(1)
    expect(runtime.reset).toHaveBeenCalledTimes(1)
  })
})
