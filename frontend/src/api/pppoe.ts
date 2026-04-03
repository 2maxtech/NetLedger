import client from './client';

export interface PPPoESession {
  sid: string;
  ifname: string;
  username: string;
  'calling-sid': string;
  ip: string;
  'rate-limit': string;
  type: string;
  state: string;
  uptime: string;
}

export const getSessions = () => client.get<PPPoESession[]>('/pppoe/sessions');
export const killSession = (sessionId: string) => client.delete(`/pppoe/sessions/${sessionId}`);
