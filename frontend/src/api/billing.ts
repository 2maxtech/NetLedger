import api from './client'

export interface Invoice {
  id: string
  customer_id: string
  customer_name: string
  plan_id: string
  plan_name: string
  amount: number | string
  total_paid: number | string
  due_date: string
  status: string
  paid_at: string | null
  issued_at: string
  created_at: string
}

export interface Payment {
  id: string
  invoice_id: string
  customer_name: string
  invoice_amount: number | string
  amount: number | string
  method: string
  reference_number: string | null
  received_by: string | null
  received_at: string
  created_at: string
}

export interface RevenueSummary {
  total_billed: number
  total_collected: number
  total_outstanding: number
  collection_rate: number
}

export function getInvoices(params?: { page?: number; size?: number; status?: string; from_date?: string; to_date?: string; customer_id?: string }) {
  return api.get<{ items: Invoice[]; total: number }>('/billing/invoices', { params })
}

export function getInvoice(id: string) {
  return api.get<Invoice>(`/billing/invoices/${id}`)
}

export function generateInvoices(customerId?: string) {
  return api.post<{ generated: number; skipped: number }>('/billing/invoices/generate', customerId ? { customer_id: customerId } : {})
}

export function updateInvoice(id: string, data: { status?: string; amount?: number }) {
  return api.put(`/billing/invoices/${id}`, data)
}

export function downloadInvoicePdf(id: string) {
  return api.get(`/billing/invoices/${id}/pdf`, { responseType: 'blob' })
}

export function deleteInvoice(id: string) {
  return api.delete(`/billing/invoices/${id}`)
}

export function getPayments(params?: { page?: number; size?: number; from_date?: string; to_date?: string }) {
  return api.get<{ items: Payment[]; total: number }>('/billing/payments', { params })
}

export function recordPayment(data: { invoice_id: string; amount: number; method: string; reference_number?: string }) {
  return api.post<Payment>('/billing/payments', data)
}

export function getRevenueSummary(from_date?: string, to_date?: string) {
  return api.get<RevenueSummary>('/billing/reports/summary', { params: { from_date, to_date } })
}
