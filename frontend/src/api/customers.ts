import api from './client'

export interface Customer {
  id: string
  full_name: string
  email: string
  phone: string
  address: string
  pppoe_username: string
  pppoe_password?: string
  status: string
  plan_id: string | null
  plan?: { id: string; name: string; monthly_price: number; download_mbps: number; upload_mbps: number }
  router_id?: string | null
  area_id?: string | null
  mac_address?: string | null
  latitude?: number | null
  longitude?: number | null
  created_at: string
}

export interface CustomerListResponse {
  items: Customer[]
  total: number
  page: number
  page_size: number
}

export function getCustomers(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
  return api.get<CustomerListResponse>('/customers/', { params })
}

export function getCustomer(id: string) {
  return api.get<Customer>(`/customers/${id}`)
}

export function createCustomer(data: Partial<Customer> & { pppoe_password?: string }) {
  return api.post<Customer>('/customers/', data)
}

export function updateCustomer(id: string, data: Partial<Customer>) {
  return api.put<Customer>(`/customers/${id}`, data)
}

export function deleteCustomer(id: string) {
  return api.delete(`/customers/${id}`)
}

export function disconnectCustomer(id: string) {
  return api.post(`/customers/${id}/disconnect`)
}

export function reconnectCustomer(id: string) {
  return api.post(`/customers/${id}/reconnect`)
}

export function throttleCustomer(id: string) {
  return api.post(`/customers/${id}/throttle`)
}

export function changePlan(id: string, planId: string) {
  return api.post(`/customers/${id}/change-plan`, { plan_id: planId })
}

export interface HistoryEvent {
  type: string
  date: string
  title: string
  detail: string | null
  status: string
  ref_id: string
}

export function getCustomerHistory(id: string) {
  return api.get<{ events: HistoryEvent[]; total: number }>(`/customers/${id}/history`)
}
