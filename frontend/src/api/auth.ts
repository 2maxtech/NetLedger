import api from './client'

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  company_name: string | null
  phone: string | null
  role: 'super_admin' | 'admin' | 'staff' | 'billing' | 'technician'
  permissions: string[]
  is_active: boolean
  is_demo: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface RegisterPayload {
  company_name: string
  full_name: string
  email: string
  phone: string
  username: string
  password: string
}

export function login(username: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { username, password })
}

export function refreshToken(refresh_token: string) {
  return api.post<TokenResponse>('/auth/refresh', { refresh_token })
}

export function getMe() {
  return api.get<User>('/auth/me')
}

export function demoLogin() {
  return api.post<TokenResponse>('/auth/demo-login')
}

export function register(data: RegisterPayload) {
  return api.post<{ id: string; username: string; email: string; message: string; email_sent: boolean }>('/auth/register', data)
}
