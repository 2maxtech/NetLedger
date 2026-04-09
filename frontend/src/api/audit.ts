import api from './client'

export interface AuditLog {
  id: string
  user_id: string | null
  user_name: string | null
  action: string
  entity_type: string
  entity_id: string | null
  details: any
  ip_address: string | null
  created_at: string
}

export function getAuditLogs(params?: { page?: number; page_size?: number; entity_type?: string; user_id?: string; date_from?: string; date_to?: string }) {
  return api.get<{ items: AuditLog[]; total: number }>('/audit-logs/', { params })
}
