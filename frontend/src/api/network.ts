import client from './client';

export interface PppoeSession {
  '.id': string;
  name: string;
  service: string;
  'caller-id': string;
  address: string;
  uptime: string;
  encoding: string;
}

export interface NetworkStatus {
  connected: boolean;
  identity?: string;
  uptime?: string;
  cpu_load?: string;
  free_memory?: string;
  error?: string;
}

export const getActiveSessions = () =>
  client.get<{ sessions: PppoeSession[]; total: number }>('/network/active-sessions');

export const getNetworkStatus = () =>
  client.get<NetworkStatus>('/network/status');

export const getSubscribers = () =>
  client.get<{ subscribers: any[]; total: number }>('/network/subscribers');

export interface DashboardData {
  subscribers: {
    total: number;
    active: number;
    suspended: number;
    disconnected: number;
  };
  billing: {
    mrr: number;
    billed_this_month: number;
    collected_this_month: number;
    collection_rate: number;
    overdue_count: number;
    overdue_amount: number;
  };
  recent_payments: Array<{
    id: string;
    amount: string;
    method: string;
    received_at: string | null;
  }>;
  revenue_trend: Array<{
    month: string;
    collected: number;
  }>;
  mikrotik: {
    connected: boolean;
    identity: string;
    uptime: string;
    cpu_load: string;
    free_memory: number;
    total_memory: number;
    active_sessions: number;
    version: string;
    interfaces: Array<{
      name: string;
      type: string;
      running: boolean;
      rx_bytes: number;
      tx_bytes: number;
    }>;
    error?: string;
  };
}

export const getDashboard = () =>
  client.get<DashboardData>('/network/dashboard');
