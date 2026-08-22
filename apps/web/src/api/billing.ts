import type { InvoiceReply } from '@generated/billing.InvoiceReply.v2'
import type { InvoiceRequest } from '@generated/billing.InvoiceRequest.v2'
import { post } from './client'

// Modelable's TypeScript ref<> output still models `encounterId` as the
// referenced object, while the API accepts its identifier on the wire.
export type InvoiceCreateInput = Omit<InvoiceRequest, 'encounterId'> & { encounterId?: string }

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
