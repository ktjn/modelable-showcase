import { describe, expect, it } from 'vitest'
import type { RuntimeRequest } from '../api/runtime-contract'
import { dispatchRoute, RouteDispatchError } from './route-adapter'

const NOW = '2026-09-01T08:00:00.000Z'
const GENERATED_ID = '9c9c57ef-3f3b-4a8e-8d0b-1c2f3a4b5c6d'

function dispatch(request: RuntimeRequest) {
  return dispatchRoute(request, NOW, () => GENERATED_ID)
}

describe('WASM route adapter', () => {
  it.each([
    {
      name: 'create patient',
      request: { method: 'POST', path: '/api/patients', body: { patientId: 'patient-1' } },
      expected: { operation: 'execute', payload: { type: 'CreatePatient', payload: { patientId: 'patient-1' }, now: NOW } },
    },
    {
      name: 'search patients',
      request: { method: 'GET', path: '/api/patients?name=Ada%20Lovelace&email=ada%40example.com' },
      expected: {
        operation: 'query',
        payload: { type: 'SearchPatients', payload: { name: 'Ada Lovelace', email: 'ada@example.com' } },
      },
    },
    {
      name: 'get patient',
      request: { method: 'GET', path: '/api/patients/patient%2D1' },
      expected: { operation: 'query', payload: { type: 'GetPatient', payload: { patientId: 'patient-1' } } },
    },
    {
      name: 'create appointment',
      request: { method: 'POST', path: '/api/appointments', body: { appointmentId: 'appointment-1' } },
      expected: {
        operation: 'execute',
        payload: { type: 'CreateAppointment', payload: { appointmentId: 'appointment-1' }, now: NOW },
      },
    },
    {
      name: 'reschedule appointment',
      request: { method: 'PATCH', path: '/api/appointments/appointment-1', body: { scheduledDate: '2026-09-02' } },
      expected: {
        operation: 'execute',
        payload: {
          type: 'RescheduleAppointment',
          payload: { appointmentId: 'appointment-1', changes: { scheduledDate: '2026-09-02' } },
          now: NOW,
        },
      },
    },
    {
      name: 'cancel appointment',
      request: { method: 'POST', path: '/api/appointments/appointment-1/cancel', body: { reason: 'patient request' } },
      expected: {
        operation: 'execute',
        payload: {
          type: 'CancelAppointment',
          payload: { appointmentId: 'appointment-1', reason: 'patient request' },
          now: NOW,
        },
      },
    },
    {
      name: 'daily schedule',
      request: { method: 'GET', path: '/api/schedule?date=2026-09-01&practitioner=practitioner-1' },
      expected: {
        operation: 'query',
        payload: {
          type: 'DailySchedule',
          payload: { date: '2026-09-01', practitionerId: 'practitioner-1' },
        },
      },
    },
    {
      name: 'patient appointments',
      request: { method: 'GET', path: '/api/patients/patient-1/appointments' },
      expected: {
        operation: 'query',
        payload: { type: 'PatientAppointments', payload: { patientId: 'patient-1' } },
      },
    },
    {
      name: 'create encounter',
      request: { method: 'POST', path: '/api/encounters', body: { encounterId: 'encounter-1' } },
      expected: {
        operation: 'execute',
        payload: { type: 'CreateEncounter', payload: { encounterId: 'encounter-1' }, now: NOW },
      },
    },
    {
      name: 'update encounter',
      request: { method: 'PATCH', path: '/api/encounters/encounter-1', body: { status: 'completed' } },
      expected: {
        operation: 'execute',
        payload: {
          type: 'UpdateEncounter',
          payload: { encounterId: 'encounter-1', changes: { status: 'completed' } },
          now: NOW,
        },
      },
    },
    {
      name: 'record observation with defaults',
      request: { method: 'POST', path: '/api/encounters/encounter-1/observations', body: { code: 'pulse' } },
      expected: {
        operation: 'execute',
        payload: {
          type: 'RecordObservation',
          payload: {
            observationId: GENERATED_ID,
            encounterId: 'encounter-1',
            code: 'pulse',
            isAbnormal: false,
            recordedAt: NOW,
          },
          now: NOW,
        },
      },
    },
    {
      name: 'create invoice',
      request: { method: 'POST', path: '/api/invoices', body: { invoiceId: 'invoice-1' } },
      expected: {
        operation: 'execute',
        payload: { type: 'CreateInvoice', payload: { invoiceId: 'invoice-1' }, now: NOW },
      },
    },
    {
      name: 'record payment with defaults',
      request: { method: 'POST', path: '/api/invoices/invoice-1/payments', body: { amount: '10.00', method: 'card' } },
      expected: {
        operation: 'execute',
        payload: {
          type: 'RecordPayment',
          payload: {
            paymentId: GENERATED_ID,
            invoiceId: 'invoice-1',
            amount: '10.00',
            method: 'card',
            receivedAt: NOW,
          },
          now: NOW,
        },
      },
    },
    {
      name: 'patient summary',
      request: { method: 'GET', path: '/api/patients/patient-1/summary' },
      expected: { operation: 'query', payload: { type: 'PatientSummary', payload: { patientId: 'patient-1' } } },
    },
    {
      name: 'clinic analytics',
      request: { method: 'GET', path: '/api/analytics/clinic' },
      expected: { operation: 'query', payload: { type: 'Analytics' } },
    },
  ] satisfies Array<{ name: string, request: RuntimeRequest, expected: unknown }>)('$name', ({ request, expected }) => {
    expect(dispatch(request)).toEqual(expected)
  })

  it('preserves caller-supplied observation and payment identity and time fields', () => {
    expect(dispatch({
      method: 'POST',
      path: '/api/encounters/encounter-1/observations',
      body: {
        observationId: 'observation-1',
        code: 'pulse',
        isAbnormal: true,
        recordedAt: '2026-08-31T12:00:00Z',
      },
    }).payload).toMatchObject({
      payload: {
        observationId: 'observation-1',
        isAbnormal: true,
        recordedAt: '2026-08-31T12:00:00Z',
      },
    })
    expect(dispatch({
      method: 'POST',
      path: '/api/invoices/invoice-1/payments',
      body: {
        paymentId: 'payment-1',
        amount: '10.00',
        method: 'cash',
        receivedAt: '2026-08-31T12:00:00Z',
      },
    }).payload).toMatchObject({
      payload: { paymentId: 'payment-1', receivedAt: '2026-08-31T12:00:00Z' },
    })
  })

  it('rejects unknown routes and non-object bodies explicitly', () => {
    expect(() => dispatch({ method: 'GET', path: '/api/unknown' })).toThrow(RouteDispatchError)
    expect(() => dispatch({ method: 'POST', path: '/api/patients', body: null })).toThrow(
      'requires a JSON object body',
    )
  })
})
