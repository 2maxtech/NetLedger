import api from './client'

export interface VoucherType {
  id: string
  code: string
  router_id: string
  hotspot_profile: string
  duration_hours: number
  status: string
  activated_at: string | null
  expires_at: string | null
  batch_id: string | null
  created_at: string
}

export interface HotspotProfile {
  name: string
  rate_limit: string
  session_timeout: string
  shared_users: string
}

export function getVouchers(params?: { status?: string; batch_id?: string }) {
  return api.get<VoucherType[]>('/vouchers/', { params })
}

export function getHotspotProfiles(routerId: string) {
  return api.get<HotspotProfile[]>('/vouchers/hotspot-profiles', { params: { router_id: routerId } })
}

export function generateVouchers(data: { count: number; router_id: string; hotspot_profile: string; duration_hours: number }) {
  return api.post<VoucherType[]>('/vouchers/generate', data)
}

export function revokeVoucher(id: string) {
  return api.delete(`/vouchers/${id}`)
}
