import client from './client';

export interface Invoice {
  id: string;
  customer_id: string;
  plan_id: string;
  amount: string;
  due_date: string;
  status: string;
  paid_at: string | null;
  issued_at: string;
  created_at: string;
  customer_name: string | null;
  plan_name: string | null;
  total_paid: string | null;
}

export interface InvoiceListResponse {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface Payment {
  id: string;
  invoice_id: string;
  amount: string;
  method: string;
  reference_number: string | null;
  received_by: string | null;
  received_at: string;
  created_at: string;
  customer_name: string | null;
  invoice_amount: string | null;
}

export interface PaymentListResponse {
  items: Payment[];
  total: number;
  page: number;
  page_size: number;
}

export interface RevenueSummary {
  total_billed: string;
  total_collected: string;
  total_outstanding: string;
  collection_rate: number;
}

export const getInvoices = (params: {
  page?: number;
  size?: number;
  customer_id?: string;
  status?: string;
  from_date?: string;
  to_date?: string;
}) => client.get<InvoiceListResponse>('/billing/invoices', { params });

export const getInvoice = (id: string) => client.get<Invoice>(`/billing/invoices/${id}`);

export const generateInvoices = (customerId?: string) =>
  client.post('/billing/invoices/generate', { customer_id: customerId || null });

export const updateInvoice = (id: string, data: { status?: string; amount?: string }) =>
  client.put(`/billing/invoices/${id}`, data);

export const getPayments = (params: {
  page?: number;
  size?: number;
  customer_id?: string;
  from_date?: string;
  to_date?: string;
}) => client.get<PaymentListResponse>('/billing/payments', { params });

export const recordPayment = (data: {
  invoice_id: string;
  amount: string;
  method: string;
  reference_number?: string;
}) => client.post<Payment>('/billing/payments', data);

export const getRevenueSummary = (params: { from_date: string; to_date: string }) =>
  client.get<RevenueSummary>('/billing/reports/summary', { params });
