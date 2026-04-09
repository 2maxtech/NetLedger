import api from './client'

export interface TicketMessage {
  id: string
  ticket_id: string
  sender_type: string
  sender_id: string | null
  sender_name?: string
  message: string
  created_at: string
}

export interface TicketType {
  id: string
  customer_id: string
  customer_name?: string
  subject: string
  status: string
  priority: string
  assigned_to: string | null
  assigned_to_name?: string | null
  resolved_at: string | null
  created_at: string
  messages?: TicketMessage[]
}

export function getTickets(params?: { status?: string; priority?: string; assigned_to?: string }) {
  return api.get<TicketType[]>('/tickets/', { params })
}

export function createTicket(data: { customer_id: string; subject: string; priority: string; message: string }) {
  return api.post<TicketType>('/tickets/', data)
}

export function getTicket(id: string) {
  return api.get<TicketType>(`/tickets/${id}`)
}

export function updateTicket(id: string, data: { status?: string; priority?: string; assigned_to?: string }) {
  return api.put<TicketType>(`/tickets/${id}`, data)
}

export function addTicketMessage(id: string, data: { message: string; sender_type?: string }) {
  return api.post<TicketMessage>(`/tickets/${id}/messages`, data)
}

export function getTicketCounts() {
  return api.get<{ open: number }>('/tickets/counts')
}
