import api from './client'

export interface RouterType {
  id: string
  name: string
  url: string
  username: string
  location?: string
  is_active: boolean
  maintenance_mode: boolean
  maintenance_message?: string
  created_at: string
}

export interface RouterStatus {
  id: string
  name: string
  connected: boolean
  identity?: string
  uptime?: string
  cpu_load?: number
  free_memory?: number
  total_memory?: number
  active_sessions?: number
  version?: string
  error?: string
}

export interface AreaType {
  id: string
  name: string
  description: string | null
  router_id: string | null
  router?: RouterType
  created_at: string
}

export function getRouters() {
  return api.get<RouterType[]>('/routers/')
}

export function createRouter(data: Partial<RouterType> & { password?: string }) {
  return api.post<RouterType>('/routers/', data)
}

export function updateRouter(id: string, data: Partial<RouterType> & { password?: string }) {
  return api.put<RouterType>(`/routers/${id}`, data)
}

export function deleteRouter(id: string) {
  return api.delete(`/routers/${id}`)
}

export function getRouterStatus(id: string) {
  return api.get<RouterStatus>(`/routers/${id}/status`)
}

export function importFromRouter(id: string) {
  return api.post(`/routers/${id}/import`)
}

export function getAreas() {
  return api.get<AreaType[]>('/areas/')
}

export function createArea(data: { name: string; description?: string; router_id?: string }) {
  return api.post<AreaType>('/areas/', data)
}

export function updateArea(id: string, data: { name?: string; description?: string; router_id?: string }) {
  return api.put<AreaType>(`/areas/${id}`, data)
}

export function deleteArea(id: string) {
  return api.delete(`/areas/${id}`)
}

// VPN
export interface VpnSetupResponse {
  tunnel_ip: string
  server_public_key: string
  endpoint: string
  script: string
  instructions: string[]
}

export interface VpnActivateResponse {
  status: string
  tunnel_ip: string
  router_url: string
  message: string
}

export interface VpnStatusResponse {
  status: string
  tunnel_ip?: string
  endpoint?: string
  latest_handshake?: number
  rx_bytes?: number
  tx_bytes?: number
}

export function vpnSetup(routerId: string) {
  return api.post<VpnSetupResponse>(`/vpn/${routerId}/setup`)
}

export function vpnActivate(routerId: string, data: { public_key: string; client_lan?: string }) {
  return api.post<VpnActivateResponse>(`/vpn/${routerId}/activate`, data)
}

export function vpnStatus(routerId: string) {
  return api.get<VpnStatusResponse>(`/vpn/${routerId}/vpn-status`)
}
