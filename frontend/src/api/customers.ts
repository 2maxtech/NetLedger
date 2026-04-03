import client from './client';

export interface Customer {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  address: string | null;
  pppoe_username: string;
  status: string;
  plan_id: string;
  plan: { id: string; name: string; download_mbps: number; upload_mbps: number; monthly_price: string; } | null;
  created_at: string;
}

export interface CustomerListResponse {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

export const getCustomers = (params: { page?: number; page_size?: number; search?: string; status?: string }) =>
  client.get<CustomerListResponse>('/customers/', { params });
export const getCustomer = (id: string) => client.get<Customer>(`/customers/${id}`);
export const createCustomer = (data: Record<string, unknown>) => client.post('/customers/', data);
export const updateCustomer = (id: string, data: Record<string, unknown>) => client.put(`/customers/${id}`, data);
export const deleteCustomer = (id: string) => client.delete(`/customers/${id}`);
export const disconnectCustomer = (id: string) => client.post(`/customers/${id}/disconnect`);
export const reconnectCustomer = (id: string) => client.post(`/customers/${id}/reconnect`);
export const throttleCustomer = (id: string) => client.post(`/customers/${id}/throttle`);
