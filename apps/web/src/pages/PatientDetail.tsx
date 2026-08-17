import type { InvoiceReply } from '@generated/billing.InvoiceReply.v2'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useParams } from 'react-router-dom'
import { addPayment, createInvoice, type PaymentInput } from '../api/billing'
import { getPatient } from '../api/patients'
import { getPatientSummary } from '../api/summary'

function money(value: string): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function PaymentForm({ invoice }: { invoice: InvoiceReply }) {
  const [amount, setAmount] = useState(invoice.total)
  const [method, setMethod] = useState<PaymentInput['method']>('card')
  const [paid, setPaid] = useState(false)

  const mutation = useMutation({
    mutationFn: () => addPayment(invoice.invoiceId, { amount, method, receivedAt: new Date().toISOString() }),
    onSuccess: () => setPaid(true),
  })

  if (paid) {
    return <p>Payment recorded for invoice {invoice.invoiceId}.</p>
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label>
        Amount
        <input value={amount} onChange={(event) => setAmount(event.target.value)} />
      </label>
      <label>
        Method
        <select value={method} onChange={(event) => setMethod(event.target.value as PaymentInput['method'])}>
          <option value="card">Card</option>
          <option value="cash">Cash</option>
          <option value="bank_transfer">Bank transfer</option>
          <option value="insurance">Insurance</option>
        </select>
      </label>
      <button type="submit" disabled={mutation.isPending}>
        Record payment
      </button>
      {mutation.isError && (
        <p role="alert">{mutation.error instanceof Error ? mutation.error.message : 'Failed to record payment.'}</p>
      )}
    </form>
  )
}

function InvoiceCreateForm({ patientId, onCreated }: { patientId: string; onCreated: (invoice: InvoiceReply) => void }) {
  const [description, setDescription] = useState('Consultation')
  const [amount, setAmount] = useState('')
  const [tax, setTax] = useState('0.00')
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => {
      const total = (money(amount) + money(tax)).toFixed(2)
      return createInvoice({
        invoiceId: crypto.randomUUID(),
        patientId,
        lines: [{ description, quantity: 1, unitPrice: amount, lineTotal: amount }],
        subtotal: amount,
        tax,
        total,
        status: 'issued',
      })
    },
    onSuccess: (invoice) => {
      onCreated(invoice)
      setAmount('')
      void queryClient.invalidateQueries({ queryKey: ['patient-summary', patientId] })
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!description.trim() || !amount.trim() || money(amount) <= 0) {
      setError('Description and a positive amount are required.')
      return
    }
    setError(null)
    mutation.mutate()
  }

  return (
    <form onSubmit={handleSubmit}>
      <label>
        Description
        <input value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <label>
        Amount
        <input value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="100.00" />
      </label>
      <label>
        Tax
        <input value={tax} onChange={(event) => setTax(event.target.value)} />
      </label>
      <button type="submit" disabled={mutation.isPending}>
        Create invoice
      </button>
      {error && <p role="alert">{error}</p>}
      {mutation.isError && (
        <p role="alert">{mutation.error instanceof Error ? mutation.error.message : 'Failed to create invoice.'}</p>
      )}
    </form>
  )
}

function PatientBilling({ patientId }: { patientId: string }) {
  const [invoices, setInvoices] = useState<InvoiceReply[]>([])

  const { data: summary, isLoading, isError, error } = useQuery({
    queryKey: ['patient-summary', patientId],
    queryFn: () => getPatientSummary(patientId),
  })

  return (
    <section>
      <h2>Billing</h2>

      {isLoading && <p>Loading billing summary…</p>}
      {isError && <p role="alert">{error instanceof Error ? error.message : 'Failed to load billing summary'}</p>}
      {summary && (
        <dl>
          <dt>Invoices</dt>
          <dd>{summary.invoiceCount}</dd>
          <dt>Total invoiced</dt>
          <dd>{summary.totalInvoiced ?? '—'}</dd>
          <dt>Total paid</dt>
          <dd>{summary.totalPaid ?? '—'}</dd>
          <dt>Outstanding</dt>
          <dd>{summary.outstanding ?? '—'}</dd>
        </dl>
      )}

      <h3>New invoice</h3>
      <InvoiceCreateForm patientId={patientId} onCreated={(invoice) => setInvoices((prev) => [...prev, invoice])} />

      {invoices.length > 0 && (
        <>
          <h3>Invoices created this session</h3>
          <ul>
            {invoices.map((invoice) => (
              <li key={invoice.invoiceId}>
                <p>
                  Invoice {invoice.invoiceId} · total {invoice.total} · status {invoice.status}
                </p>
                <PaymentForm invoice={invoice} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export function PatientDetail() {
  const { id } = useParams<{ id: string }>()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['patient', id],
    queryFn: () => getPatient(id as string),
    enabled: Boolean(id),
  })

  if (isLoading) {
    return <p>Loading patient…</p>
  }
  if (isError) {
    return <p role="alert">{error instanceof Error ? error.message : 'Failed to load patient'}</p>
  }
  if (!data) {
    return null
  }

  return (
    <section>
      <h1>{data.legalName}</h1>
      <dl>
        <dt>Patient ID</dt>
        <dd>{data.patientId}</dd>
        <dt>Preferred name</dt>
        <dd>{data.preferredName || '—'}</dd>
        <dt>Date of birth</dt>
        <dd>{data.dateOfBirth}</dd>
        <dt>Email</dt>
        <dd>{data.contact?.email ?? '—'}</dd>
        <dt>Phone</dt>
        <dd>{data.contact?.phone ?? '—'}</dd>
        <dt>Address</dt>
        <dd>
          {data.address
            ? `${data.address.street}, ${data.address.city} ${data.address.postalCode}, ${data.address.country}`
            : '—'}
        </dd>
        <dt>Preferred language</dt>
        <dd>{data.preferredLanguage}</dd>
      </dl>

      <PatientBilling patientId={data.patientId} />
    </section>
  )
}
