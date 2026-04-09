import api from './client'

export interface StaffUser {
  id: string
  username: string
  email: string
  full_name: string | null
  company_name: string | null
  phone: string | null
  role: string
  permissions: string[]
  is_active: boolean
  created_at: string
}

export interface PermissionModule {
  key: string
  label: string
}

export function getUsers() {
  return api.get<StaffUser[]>('/system/users/')
}

export function getPermissionModules() {
  return api.get<PermissionModule[]>('/system/users/permissions')
}

export function createUser(data: { username: string; email: string; password: string; role: string; permissions?: string[] }) {
  return api.post<StaffUser>('/system/users/', data)
}

export function updateUser(id: string, data: { username?: string; email?: string; password?: string; role?: string; permissions?: string[]; is_active?: boolean }) {
  return api.put<StaffUser>(`/system/users/${id}`, data)
}

export function deleteUser(id: string) {
  return api.delete(`/system/users/${id}`)
}

export function getOrganizations() {
  return api.get<StaffUser[]>('/system/organizations/')
}
