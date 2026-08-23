import type { RuntimeMethod, RuntimeRequest } from '../api/runtime-contract'

export interface RouteDispatch {
  operation: 'execute' | 'query'
  payload: Record<string, unknown>
}

type IdFactory = () => string

export class RouteDispatchError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RouteDispatchError'
  }
}

function requestBody(request: RuntimeRequest): Record<string, unknown> {
  if (typeof request.body !== 'object' || request.body === null || Array.isArray(request.body))
    throw new RouteDispatchError(`${request.method} ${request.path} requires a JSON object body`)
  return request.body as Record<string, unknown>
}

function decodeId(value: string): string {
  try {
    return decodeURIComponent(value)
  }
  catch {
    throw new RouteDispatchError(`invalid encoded route identifier '${value}'`)
  }
}

function command(type: string, payload: unknown, now: string): RouteDispatch {
  return { operation: 'execute', payload: { type, payload, now } }
}

function query(type: string, payload?: unknown): RouteDispatch {
  return {
    operation: 'query',
    payload: payload === undefined ? { type } : { type, payload },
  }
}

function methodPath(method: RuntimeMethod, pathname: string): string {
  return `${method} ${pathname}`
}

/** Translate the finite browser API surface into the Rust runtime ABI. */
export function dispatchRoute(
  request: RuntimeRequest,
  now: string,
  newId: IdFactory,
): RouteDispatch {
  const queryStart = request.path.indexOf('?')
  const pathname = queryStart === -1 ? request.path : request.path.slice(0, queryStart)
  const parameters = new URLSearchParams(queryStart === -1 ? '' : request.path.slice(queryStart + 1))
  const route = methodPath(request.method, pathname)

  if (route === 'POST /api/patients')
    return command('CreatePatient', requestBody(request), now)
  if (route === 'GET /api/patients') {
    return query('SearchPatients', {
      ...(parameters.has('name') ? { name: parameters.get('name') } : {}),
      ...(parameters.has('email') ? { email: parameters.get('email') } : {}),
    })
  }
  if (route === 'POST /api/appointments')
    return command('CreateAppointment', requestBody(request), now)
  if (route === 'GET /api/schedule') {
    return query('DailySchedule', {
      date: parameters.get('date'),
      ...(parameters.has('practitioner')
        ? { practitionerId: parameters.get('practitioner') }
        : {}),
    })
  }
  if (route === 'POST /api/encounters')
    return command('CreateEncounter', requestBody(request), now)
  if (route === 'POST /api/invoices')
    return command('CreateInvoice', requestBody(request), now)
  if (route === 'GET /api/analytics/clinic')
    return query('Analytics')

  let match = /^\/api\/patients\/([^/]+)\/summary$/.exec(pathname)
  if (request.method === 'GET' && match)
    return query('PatientSummary', { patientId: decodeId(match[1]!) })

  match = /^\/api\/patients\/([^/]+)\/appointments$/.exec(pathname)
  if (request.method === 'GET' && match)
    return query('PatientAppointments', { patientId: decodeId(match[1]!) })

  match = /^\/api\/patients\/([^/]+)$/.exec(pathname)
  if (request.method === 'GET' && match)
    return query('GetPatient', { patientId: decodeId(match[1]!) })

  match = /^\/api\/appointments\/([^/]+)\/cancel$/.exec(pathname)
  if (request.method === 'POST' && match) {
    const body = requestBody(request)
    return command('CancelAppointment', {
      appointmentId: decodeId(match[1]!),
      reason: body.reason,
    }, now)
  }

  match = /^\/api\/appointments\/([^/]+)$/.exec(pathname)
  if (request.method === 'PATCH' && match) {
    return command('RescheduleAppointment', {
      appointmentId: decodeId(match[1]!),
      changes: requestBody(request),
    }, now)
  }

  match = /^\/api\/encounters\/([^/]+)\/observations$/.exec(pathname)
  if (request.method === 'POST' && match) {
    const body = requestBody(request)
    return command('RecordObservation', {
      ...body,
      observationId: body.observationId ?? newId(),
      encounterId: decodeId(match[1]!),
      isAbnormal: body.isAbnormal ?? false,
      recordedAt: body.recordedAt ?? now,
    }, now)
  }

  match = /^\/api\/encounters\/([^/]+)$/.exec(pathname)
  if (request.method === 'PATCH' && match) {
    return command('UpdateEncounter', {
      encounterId: decodeId(match[1]!),
      changes: requestBody(request),
    }, now)
  }

  match = /^\/api\/invoices\/([^/]+)\/payments$/.exec(pathname)
  if (request.method === 'POST' && match) {
    const body = requestBody(request)
    return command('RecordPayment', {
      ...body,
      paymentId: body.paymentId ?? newId(),
      invoiceId: decodeId(match[1]!),
      receivedAt: body.receivedAt ?? now,
    }, now)
  }

  throw new RouteDispatchError(`unsupported showcase route ${route}`)
}

export function isRuntimeRequest(value: unknown): value is RuntimeRequest {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    return false
  const candidate = value as Record<string, unknown>
  return (candidate.method === 'GET' || candidate.method === 'POST' || candidate.method === 'PATCH')
    && typeof candidate.path === 'string'
}
