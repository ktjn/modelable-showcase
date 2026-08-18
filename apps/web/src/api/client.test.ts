import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, get, post } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client (camelCase wire format, UPSTREAM_FINDINGS.md #39 fixed in Modelable 1.9.4)', () => {
  it('post() sends the request body as JSON unmodified', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { patientId: 'p-1', legalName: 'Ada' }))
    vi.stubGlobal('fetch', fetchMock)

    await post('/api/patients', { patientId: 'p-1', legalName: 'Ada', contact: { email: 'a@example.com' } })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const sentBody: unknown = JSON.parse(init.body as string)
    expect(sentBody).toEqual({ patientId: 'p-1', legalName: 'Ada', contact: { email: 'a@example.com' } })
  })

  it('get() returns the response body unmodified', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { patientId: 'p-1', legalName: 'Ada' }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await get<{ patientId: string; legalName: string }>('/api/patients/p-1')

    expect(result).toEqual({ patientId: 'p-1', legalName: 'Ada' })
  })

  it('preserves nested objects and arrays of objects unmodified', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        patientId: 'p-1',
        contact: { email: 'a@example.com', phone: '555' },
        lines: [{ unitPrice: '10.00' }, { unitPrice: '20.00' }],
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await get<unknown>('/api/whatever')

    expect(result).toEqual({
      patientId: 'p-1',
      contact: { email: 'a@example.com', phone: '555' },
      lines: [{ unitPrice: '10.00' }, { unitPrice: '20.00' }],
    })
  })

  it('throws ApiError with the server-provided message on a non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(409, { error: 'patient already exists' }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(get('/api/patients/p-1')).rejects.toMatchObject({
      status: 409,
      message: 'patient already exists',
    })
  })
})

describe('ApiError', () => {
  it('is an instance of Error carrying the HTTP status and raw body', () => {
    const error = new ApiError(404, { error: 'not found' })
    expect(error).toBeInstanceOf(Error)
    expect(error.status).toBe(404)
    expect(error.body).toEqual({ error: 'not found' })
  })
})
