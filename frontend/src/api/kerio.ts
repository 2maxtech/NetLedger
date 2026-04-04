import client from './client';

export interface ActiveHost {
  connections: number;
  activityRule: string;
  name: string;
  macAddress: string;
  ipAddress: string;
  ipAddressFromDHCP: boolean;
  loginTime: string;
  user: {
    id: string;
    name: string;
    isGroup: boolean;
    domainName: string;
  };
}

export interface KerioStatus {
  connected: boolean;
  interfaces?: number;
  error?: string;
}

export const getActiveHosts = () => client.get<{ hosts: ActiveHost[]; total: number }>('/kerio/active-hosts');
export const getKerioStatus = () => client.get<KerioStatus>('/kerio/status');
export const getKerioUsers = () => client.get<{ users: any[]; total: number }>('/kerio/users');
