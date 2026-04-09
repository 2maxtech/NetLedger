import { portalApi } from './client'

export interface PortalCustomer {
  id: string
  full_name: string
  email: string
  phone: string
  status: string
  plan_name: string
}

export interface PortalDashboard {
  status: string
  plan: { name: string; download_mbps: number; upload_mbps: number; monthly_price: number }
  outstanding_balance: number
  session: { address: string; uptime: string; bytes_in: number; bytes_out: number } | null
  recent_invoices: Array<{ id: string; amount: number; due_date: string; status: string; payment_token?: string }>
}

export interface PortalInvoice {
  id: string
  amount: number | string
  total_paid: number | string
  due_date: string
  status: string
  issued_at: string
  paid_at: string | null
  plan_name: string
  payment_token?: string
}

export function resolveTenantSlug(slug: string) {
  return portalApi.get<{ tenant_id: string; company_name: string; company_logo_url: string }>(`/tenant/${slug}`)
}

export function portalLogin(username: string, password: string, slug: string) {
  return portalApi.post('/auth/login', { username, password, slug })
}

export function getPortalMe() {
  return portalApi.get<PortalCustomer>('/me')
}

export function getPortalDashboard() {
  return portalApi.get<PortalDashboard>('/dashboard')
}

export function getPortalInvoices(params?: { page?: number; size?: number }) {
  return portalApi.get<{ items: PortalInvoice[]; total: number }>('/invoices', { params })
}

export function downloadPortalInvoicePdf(id: string) {
  return portalApi.get(`/invoices/${id}/pdf`, { responseType: 'blob' })
}

export function getPortalUsage(days?: number) {
  return portalApi.get('/usage', { params: { days } })
}

export function getPortalSessions(params?: { page?: number; size?: number }) {
  return portalApi.get('/sessions', { params })
}

export function getPortalTicketCounts() {
  return portalApi.get<{ open: number }>('/tickets/counts')
}

export function getPortalTickets() {
  return portalApi.get('/tickets')
}

export function createPortalTicket(data: { subject: string; message: string; priority?: string }) {
  return portalApi.post('/tickets', data)
}

export function getPortalTicket(id: string) {
  return portalApi.get(`/tickets/${id}`)
}

export function addPortalTicketMessage(id: string, data: { message: string }) {
  return portalApi.post(`/tickets/${id}/messages`, data)
}
