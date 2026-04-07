import api from './client'

interface BulkResponse {
  success: number
  failed: number
  errors: Array<{ id: string; error: string }>
}

export function bulkGenerateInvoices(customerIds: string[]) {
  return api.post<BulkResponse>('/customers/bulk/generate-invoices', { customer_ids: customerIds })
}
export function bulkSendReminder(customerIds: string[]) {
  return api.post<BulkResponse>('/customers/bulk/send-reminder', { customer_ids: customerIds })
}
export function bulkChangeStatus(customerIds: string[], status: string) {
  return api.post<BulkResponse>('/customers/bulk/change-status', { customer_ids: customerIds, status })
}
export function bulkMarkPaid(invoiceIds: string[]) {
  return api.post<BulkResponse>('/billing/invoices/bulk/mark-paid', { invoice_ids: invoiceIds })
}
export function bulkSendNotification(invoiceIds: string[]) {
  return api.post<BulkResponse>('/billing/invoices/bulk/send-notification', { invoice_ids: invoiceIds })
}
export function bulkDeleteInvoices(invoiceIds: string[], password: string) {
  return api.post<BulkResponse>('/billing/invoices/bulk/delete', { invoice_ids: invoiceIds, password })
}
