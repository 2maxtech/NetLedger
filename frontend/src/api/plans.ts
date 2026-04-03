import client from './client';

export interface Plan {
  id: string;
  name: string;
  download_mbps: number;
  upload_mbps: number;
  monthly_price: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export const getPlans = (params?: { active_only?: boolean }) => client.get<Plan[]>('/plans/', { params });
export const getPlan = (id: string) => client.get<Plan>(`/plans/${id}`);
export const createPlan = (data: Record<string, unknown>) => client.post('/plans/', data);
export const updatePlan = (id: string, data: Record<string, unknown>) => client.put(`/plans/${id}`, data);
export const deletePlan = (id: string) => client.delete(`/plans/${id}`);
