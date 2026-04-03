import client from './client';

export interface LoginRequest { username: string; password: string; }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string; }
export interface User { id: string; username: string; email: string; role: 'admin' | 'billing' | 'technician'; is_active: boolean; created_at: string; }

export const login = (data: LoginRequest) => client.post<TokenResponse>('/auth/login', data);
export const refreshToken = (refresh_token: string) => client.post<TokenResponse>('/auth/refresh', { refresh_token });
export const getMe = () => client.get<User>('/auth/me');
