import api from './client'

export interface SmtpSettings {
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password: string
  smtp_from: string
  smtp_from_name: string
}

export interface SmsSettings {
  sms_provider: string
  sms_api_key: string
  sms_sender_name: string
}

export function getSmtpSettings() {
  return api.get<SmtpSettings>('/settings/smtp')
}

export function saveSmtpSettings(data: SmtpSettings) {
  return api.put('/settings/smtp', data)
}

export function testSmtp(data: { to: string }) {
  return api.post('/settings/smtp/test', data)
}

export function getSmsSettings() {
  return api.get<SmsSettings>('/settings/sms')
}

export function saveSmsSettings(data: SmsSettings) {
  return api.put('/settings/sms', data)
}

export function testSms(data: { phone: string }) {
  return api.post('/settings/sms/test', data)
}

export interface BrandingSettings {
  company_name: string
  company_address: string
  company_phone: string
  company_email: string
  company_logo_url: string
  invoice_footer: string
  invoice_prefix: string
  portal_slug: string
}

export function getBrandingSettings() {
  return api.get<BrandingSettings>('/settings/branding')
}

export function saveBrandingSettings(data: Record<string, string>) {
  return api.put('/settings/branding', data)
}

export function uploadLogo(formData: FormData) {
  return api.post<{ status: string; url: string }>('/settings/branding/logo', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Billing Settings
export interface BillingSettingsType {
  billing_reminder_days_before_due: string
  billing_throttle_days_after_due: string
  billing_disconnect_days_after_due: string
  billing_terminate_days_after_due: string
  billing_default_due_day: string
  billing_auto_generate: string
  billing_send_invoice_email: string
  billing_send_invoice_sms: string
}

export function getBillingSettings() {
  return api.get<BillingSettingsType>('/settings/billing')
}

export function saveBillingSettings(data: Record<string, string>) {
  return api.put('/settings/billing', data)
}

// Account / Profile
export interface ProfileUpdate {
  username?: string
  email?: string
  full_name?: string
  company_name?: string
  phone?: string
  current_password?: string
  new_password?: string
}

export function getProfile() {
  return api.get<{
    id: string
    username: string
    email: string
    full_name: string | null
    company_name: string | null
    phone: string | null
    role: string
    is_active: boolean
    created_at: string
  }>('/auth/me')
}

export function updateProfile(data: ProfileUpdate) {
  return api.put('/auth/profile', data)
}

// Notification Templates
export interface NotificationTemplates {
  tpl_invoice_email_subject: string
  tpl_invoice_email_body: string
  tpl_invoice_sms: string
  tpl_reminder_sms: string
  tpl_overdue_email_subject: string
  tpl_overdue_email_body: string
  tpl_overdue_sms: string
}

export function getNotificationTemplates() {
  return api.get<NotificationTemplates>('/settings/notifications')
}

export function saveNotificationTemplates(data: Record<string, string>) {
  return api.put('/settings/notifications', data)
}
