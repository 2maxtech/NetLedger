import axios from 'axios';

export interface SystemStats {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  uptime_seconds: number;
}

export const getSystemStats = () =>
  axios.get<SystemStats>('/agent/system/stats', {
    headers: { 'X-API-Key': 'dev-gateway-key-2maxnet' },
    timeout: 5000,
  });
