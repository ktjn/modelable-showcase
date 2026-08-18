import type { InvoiceReply } from '@generated/billing.InvoiceReply.v2'
import type { InvoiceRequest } from '@generated/billing.InvoiceRequest.v2'
import { post } from './client'

// UPSTREAM_FINDINGS.md #38/#40: same ref<>/optionality corrections as
// appointments.ts/encounters.ts - Invoice.encounterId is
// ref<clinical.Encounter@1>.
export type InvoiceCreateInput = Omit<
  InvoiceRequest,
  'encounterId' | 'currency' | 'billingPeriod' | 'issuedAt' | 'dueDate'
> &
  Partial<{ encounterId: string; currency: string; billingPeriod: string; issuedAt: string; dueDate: string }>

export function createInvoice(request: InvoiceCreateInput): Promise<InvoiceReply> {
  return post<InvoiceReply>('/api/invoices', request)
}

export interface PaymentInput {
  paymentId?: string
  amount: string
  method: 'card' | 'cash' | 'bank_transfer' | 'insurance'
  receivedAt?: string
}

export interface PaymentReply {
  paymentId: string
  invoiceId: string
  amount: string
  method: string
  receivedAt: string
}

export function addPayment(invoiceId: string, payment: PaymentInput): Promise<PaymentReply> {
  return post<PaymentReply>(`/api/invoices/${encodeURIComponent(invoiceId)}/payments`, payment)
}
