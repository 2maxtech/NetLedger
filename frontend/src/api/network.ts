import api from './client'

export interface PppoeSession {
  '.id': string
  name: string
  service: string
  'caller-id': string
  address: string
  uptime: string
  encoding: string
}

export interface NetworkStatus {
  connected: boolean
  identity: string
  uptime: string
  cpu_load: number
  free_memory: number
  total_memory: number
}

export interface DashboardData {
  subscribers: {
    total: number
    active: number
    suspended: number
    disconnected: number
  }
  billing: {
    mrr: number
    billed_this_month: number
    collected_this_month: number
    collection_rate: number
    overdue_count: number
    overdue_amount: number
  }
  recent_payments: Array<{
    id: string
    customer_name: string
    amount: number
    method: string
    received_at: string
  }>
  revenue_trend: Array<{
    month: string
    billed: number
    collected: number
  }>
  mikrotik: {
    connected: boolean
    identity: string
    uptime: string
    cpu_load: number
    free_memory: number
    total_memory: number
    active_sessions: number
    version: string
    interfaces?: Array<{ name: string; type?: string; running?: boolean; tx_bytes: number; rx_bytes: number }>
  }
}

export function getDashboard() {
  return api.get<DashboardData>('/network/dashboard')
}

export function getActiveSessions(routerId?: string) {
  return api.get<PppoeSession[]>('/network/active-sessions', { params: routerId ? { router_id: routerId } : {} })
}

export function getNetworkStatus() {
  return api.get<NetworkStatus>('/network/status')
}

export function getSubscribers() {
  return api.get('/network/subscribers')
}

export function importSubscribers() {
  return api.post('/network/import')
}

export function scanNetwork(data: { subnet: string; timeout?: number }) {
  return api.post('/network/scan', data)
}

export function getHotspotUsers(routerId?: string) {
  return api.get('/network/hotspot/users', { params: routerId ? { router_id: routerId } : {} })
}

export function getHotspotSessions(routerId?: string) {
  return api.get('/network/hotspot/sessions', { params: routerId ? { router_id: routerId } : {} })
}

export function getHotspotProfiles(routerId: string) {
  return api.get('/network/hotspot/profiles', { params: { router_id: routerId } })
}

export function createHotspotProfile(data: { router_id: string; name: string; rate_limit?: string; session_timeout?: string; shared_users?: string; address_pool?: string }) {
  return api.post('/network/hotspot/profiles', data)
}

export function updateHotspotProfile(profileId: string, data: { router_id: string; name?: string; rate_limit?: string; session_timeout?: string; shared_users?: string; address_pool?: string }) {
  return api.patch(`/network/hotspot/profiles/${profileId}`, data)
}

export function deleteHotspotProfile(profileId: string, routerId: string) {
  return api.delete(`/network/hotspot/profiles/${profileId}`, { params: { router_id: routerId } })
}
