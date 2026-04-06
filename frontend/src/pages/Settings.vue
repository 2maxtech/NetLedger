<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import {
  getSmtpSettings,
  saveSmtpSettings,
  testSmtp,
  getSmsSettings,
  saveSmsSettings,
  testSms,
  getBrandingSettings,
  saveBrandingSettings,
  uploadLogo,
  getBillingSettings,
  saveBillingSettings,
  getProfile,
  updateProfile,
  getNotificationTemplates,
  saveNotificationTemplates,
  type SmtpSettings,
  type SmsSettings,
  type BrandingSettings,
  type BillingSettingsType,
  type ProfileUpdate,
  type NotificationTemplates,
} from '../api/settings'

const { user } = useAuth()
import { useImpersonate } from '../composables/useImpersonate'
const { isImpersonating } = useImpersonate()
const isSuperAdmin = computed(() => user.value?.role === 'super_admin' && !isImpersonating.value)
const activeTab = ref<'account' | 'billing' | 'smtp' | 'sms' | 'branding' | 'notifications' | 'libreqos'>(isImpersonating.value ? 'billing' : 'account')

// SMTP
const smtp = ref<SmtpSettings>({
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_from: '',
  smtp_from_name: '',
})
const smtpLoading = ref(false)
const smtpSaving = ref(false)
const smtpMsg = ref('')
const smtpMsgType = ref<'success' | 'error'>('success')

// SMTP Test
const testEmail = ref('')
const smtpTesting = ref(false)
const smtpTestMsg = ref('')
const smtpTestMsgType = ref<'success' | 'error'>('success')

// SMS
const sms = ref<SmsSettings>({
  sms_provider: '',
  sms_api_key: '',
  sms_sender_name: '',
})
const smsLoading = ref(false)
const smsSaving = ref(false)
const smsMsg = ref('')
const smsMsgType = ref<'success' | 'error'>('success')

// SMS Test
const testNumber = ref('')
const smsTesting = ref(false)
const smsTestMsg = ref('')
const smsTestMsgType = ref<'success' | 'error'>('success')

// Branding
const branding = ref<BrandingSettings>({
  company_name: '',
  company_address: '',
  company_phone: '',
  company_email: '',
  company_logo_url: '',
  invoice_footer: '',
  invoice_prefix: '',
  portal_slug: '',
})
const portalUrl = computed(() => branding.value.portal_slug ? `${window.location.origin}/portal/${branding.value.portal_slug}` : '')
function copyPortalUrl() { navigator.clipboard.writeText(portalUrl.value) }
const brandingLoading = ref(false)
const brandingSaving = ref(false)
const brandingMsg = ref('')
const brandingMsgType = ref<'success' | 'error'>('success')
const logoUploading = ref(false)

// Billing
const billing = ref<BillingSettingsType>({
  billing_reminder_days_before_due: '5',
  billing_throttle_days_after_due: '3',
  billing_disconnect_days_after_due: '5',
  billing_terminate_days_after_due: '35',
  billing_default_due_day: '15',
  billing_auto_generate: 'true',
  billing_send_invoice_email: 'true',
  billing_send_invoice_sms: 'true',
})
const billingLoading = ref(false)
const billingSaving = ref(false)
const billingMsg = ref('')
const billingMsgType = ref<'success' | 'error'>('success')

// LibreQoS
const libreqosToken = ref<string | null>(null)
const libreqosLoading = ref(false)
const libreqosGenerating = ref(false)
const libreqosCopied = ref(false)
const libreqosUrl = computed(() => libreqosToken.value ? `${window.location.origin}/api/v1/libreqos/shaped-devices.csv?token=${libreqosToken.value}` : '')

// Notification Templates
const templates = ref<NotificationTemplates>({
  tpl_invoice_email_subject: '',
  tpl_invoice_email_body: '',
  tpl_invoice_sms: '',
  tpl_reminder_sms: '',
  tpl_overdue_email_subject: '',
  tpl_overdue_email_body: '',
  tpl_overdue_sms: '',
})
const templatesLoading = ref(false)
const templatesSaving = ref(false)
const templatesMsg = ref('')
const templatesMsgType = ref<'success' | 'error'>('success')

// Account
const account = ref({
  username: '',
  email: '',
  full_name: '',
  company_name: '',
  phone: '',
})
const accountLoading = ref(false)
const accountSaving = ref(false)
const accountMsg = ref('')
const accountMsgType = ref<'success' | 'error'>('success')
const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const passwordSaving = ref(false)
const passwordMsg = ref('')
const passwordMsgType = ref<'success' | 'error'>('success')

async function loadAccount() {
  accountLoading.value = true
  try {
    const { data } = await getProfile()
    account.value = {
      username: data.username,
      email: data.email,
      full_name: data.full_name || '',
      company_name: data.company_name || '',
      phone: data.phone || '',
    }
  } catch {
    accountMsg.value = 'Failed to load account'
    accountMsgType.value = 'error'
  } finally {
    accountLoading.value = false
  }
}

async function handleSaveAccount() {
  accountSaving.value = true
  accountMsg.value = ''
  try {
    const { data } = await updateProfile({
      username: account.value.username,
      email: account.value.email,
      full_name: account.value.full_name,
      company_name: account.value.company_name,
      phone: account.value.phone,
    })
    if (data.email_change_pending) {
      accountMsg.value = data.message || `Confirmation email sent to ${data.email_change_pending}. Check your inbox.`
      accountMsgType.value = 'success'
      // Revert email field to current email (not changed yet)
      account.value.email = data.email
    } else {
      accountMsg.value = 'Account updated successfully'
      accountMsgType.value = 'success'
    }
  } catch (e: any) {
    accountMsg.value = e.response?.data?.detail || 'Failed to update account'
    accountMsgType.value = 'error'
  } finally {
    accountSaving.value = false
  }
}

async function handleChangePassword() {
  passwordMsg.value = ''
  if (!currentPassword.value || !newPassword.value) {
    passwordMsg.value = 'Please fill in both current and new password'
    passwordMsgType.value = 'error'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordMsg.value = 'New passwords do not match'
    passwordMsgType.value = 'error'
    return
  }
  if (newPassword.value.length < 6) {
    passwordMsg.value = 'New password must be at least 6 characters'
    passwordMsgType.value = 'error'
    return
  }
  passwordSaving.value = true
  try {
    await updateProfile({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    passwordMsg.value = 'Password changed successfully'
    passwordMsgType.value = 'success'
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e: any) {
    passwordMsg.value = e.response?.data?.detail || 'Failed to change password'
    passwordMsgType.value = 'error'
  } finally {
    passwordSaving.value = false
  }
}

async function handleLogoUpload(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  const file = input.files[0]
  logoUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await uploadLogo(formData)
    branding.value.company_logo_url = data.url
    brandingMsg.value = 'Logo uploaded successfully'
    brandingMsgType.value = 'success'
  } catch (e: any) {
    brandingMsg.value = e.response?.data?.detail || 'Failed to upload logo'
    brandingMsgType.value = 'error'
  } finally {
    logoUploading.value = false
    input.value = ''
  }
}

async function loadSmtp() {
  smtpLoading.value = true
  try {
    const { data } = await getSmtpSettings()
    smtp.value = data
  } catch (e: any) {
    smtpMsg.value = 'Failed to load SMTP settings'
    smtpMsgType.value = 'error'
  } finally {
    smtpLoading.value = false
  }
}

async function handleSaveSmtp() {
  smtpSaving.value = true
  smtpMsg.value = ''
  try {
    await saveSmtpSettings(smtp.value)
    smtpMsg.value = 'SMTP settings saved successfully'
    smtpMsgType.value = 'success'
  } catch (e: any) {
    smtpMsg.value = e.response?.data?.detail || 'Failed to save SMTP settings'
    smtpMsgType.value = 'error'
  } finally {
    smtpSaving.value = false
  }
}

async function handleTestSmtp() {
  if (!testEmail.value) return
  smtpTesting.value = true
  smtpTestMsg.value = ''
  try {
    await testSmtp({ to: testEmail.value })
    smtpTestMsg.value = 'Test email sent successfully'
    smtpTestMsgType.value = 'success'
  } catch (e: any) {
    smtpTestMsg.value = e.response?.data?.detail || 'Failed to send test email'
    smtpTestMsgType.value = 'error'
  } finally {
    smtpTesting.value = false
  }
}

async function loadSms() {
  smsLoading.value = true
  try {
    const { data } = await getSmsSettings()
    sms.value = data
  } catch (e: any) {
    smsMsg.value = 'Failed to load SMS settings'
    smsMsgType.value = 'error'
  } finally {
    smsLoading.value = false
  }
}

async function handleSaveSms() {
  smsSaving.value = true
  smsMsg.value = ''
  try {
    await saveSmsSettings(sms.value)
    smsMsg.value = 'SMS settings saved successfully'
    smsMsgType.value = 'success'
  } catch (e: any) {
    smsMsg.value = e.response?.data?.detail || 'Failed to save SMS settings'
    smsMsgType.value = 'error'
  } finally {
    smsSaving.value = false
  }
}

async function handleTestSms() {
  if (!testNumber.value) return
  smsTesting.value = true
  smsTestMsg.value = ''
  try {
    await testSms({ phone: testNumber.value })
    smsTestMsg.value = 'Test SMS sent successfully'
    smsTestMsgType.value = 'success'
  } catch (e: any) {
    smsTestMsg.value = e.response?.data?.detail || 'Failed to send test SMS'
    smsTestMsgType.value = 'error'
  } finally {
    smsTesting.value = false
  }
}

async function loadBranding() {
  brandingLoading.value = true
  try {
    const { data } = await getBrandingSettings()
    branding.value = { ...branding.value, ...data }
  } catch (e: any) {
    brandingMsg.value = 'Failed to load branding settings'
    brandingMsgType.value = 'error'
  } finally {
    brandingLoading.value = false
  }
}

async function handleSaveBranding() {
  brandingSaving.value = true
  brandingMsg.value = ''
  try {
    await saveBrandingSettings(branding.value as unknown as Record<string, string>)
    await loadBranding()
    brandingMsg.value = 'Branding settings saved successfully'
    brandingMsgType.value = 'success'
  } catch (e: any) {
    brandingMsg.value = e.response?.data?.detail || 'Failed to save branding settings'
    brandingMsgType.value = 'error'
  } finally {
    brandingSaving.value = false
  }
}

async function loadBilling() {
  billingLoading.value = true
  try {
    const { data } = await getBillingSettings()
    billing.value = { ...billing.value, ...data }
  } catch (e: any) {
    billingMsg.value = 'Failed to load billing settings'
    billingMsgType.value = 'error'
  } finally {
    billingLoading.value = false
  }
}

async function handleSaveBilling() {
  billingSaving.value = true
  billingMsg.value = ''
  try {
    await saveBillingSettings(billing.value as unknown as Record<string, string>)
    billingMsg.value = 'Billing settings saved successfully'
    billingMsgType.value = 'success'
  } catch (e: any) {
    billingMsg.value = e.response?.data?.detail || 'Failed to save billing settings'
    billingMsgType.value = 'error'
  } finally {
    billingSaving.value = false
  }
}

async function loadLibreqos() {
  libreqosLoading.value = true
  try {
    const { data } = await import('../api/client').then(m => m.default.get('/settings/libreqos'))
    libreqosToken.value = data.token
  } catch (e) {
    console.error('Failed to load LibreQoS settings', e)
  } finally {
    libreqosLoading.value = false
  }
}

async function generateLibreqosToken() {
  libreqosGenerating.value = true
  try {
    const { data } = await import('../api/client').then(m => m.default.post('/settings/libreqos/token'))
    libreqosToken.value = data.token
  } catch (e) {
    console.error('Failed to generate token', e)
  } finally {
    libreqosGenerating.value = false
  }
}

function copyLibreqosUrl() {
  navigator.clipboard.writeText(libreqosUrl.value)
  libreqosCopied.value = true
  setTimeout(() => { libreqosCopied.value = false }, 2000)
}

async function loadTemplates() {
  templatesLoading.value = true
  try {
    const { data } = await getNotificationTemplates()
    templates.value = { ...templates.value, ...data }
  } catch {
    templatesMsg.value = 'Failed to load notification templates'
    templatesMsgType.value = 'error'
  } finally {
    templatesLoading.value = false
  }
}

async function handleSaveTemplates() {
  templatesSaving.value = true
  templatesMsg.value = ''
  try {
    await saveNotificationTemplates(templates.value as unknown as Record<string, string>)
    templatesMsg.value = 'Notification templates saved successfully'
    templatesMsgType.value = 'success'
  } catch (e: any) {
    templatesMsg.value = e.response?.data?.detail || 'Failed to save templates'
    templatesMsgType.value = 'error'
  } finally {
    templatesSaving.value = false
  }
}

onMounted(() => {
  loadAccount()
  loadBilling()
  loadSmtp()
  loadSms()
  loadBranding()
  loadTemplates()
  loadLibreqos()
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Settings</h1>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-gray-200">
      <button
        v-if="!isImpersonating"
        @click="activeTab = 'account'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'account'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        Account
      </button>
      <button
        v-if="!isSuperAdmin"
        @click="activeTab = 'billing'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'billing'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        Billing
      </button>
      <button
        @click="activeTab = 'smtp'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'smtp'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        SMTP
      </button>
      <button
        v-if="!isSuperAdmin"
        @click="activeTab = 'sms'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'sms'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        SMS
      </button>
      <button
        v-if="!isSuperAdmin"
        @click="activeTab = 'branding'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'branding'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        Branding
      </button>
      <button
        v-if="!isSuperAdmin"
        @click="activeTab = 'notifications'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'notifications'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        Notifications
      </button>
      <button
        v-if="!isSuperAdmin"
        @click="activeTab = 'libreqos'"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === 'libreqos'
            ? 'border-primary text-primary'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        LibreQoS
      </button>
    </div>

    <!-- Account Tab -->
    <div v-if="activeTab === 'account'" class="space-y-6">
      <!-- Profile -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Profile Information</h2>

        <div
          v-if="accountMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            accountMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ accountMsg }}
        </div>

        <div v-if="accountLoading" class="space-y-4">
          <div v-for="i in 5" :key="i" class="h-10 bg-gray-100 rounded-lg animate-pulse" />
        </div>

        <form v-else @submit.prevent="handleSaveAccount" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
              <input
                v-model="account.username"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <input
                v-model="account.email"
                type="email"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
              <input
                v-model="account.full_name"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Phone</label>
              <input
                v-model="account.phone"
                type="text"
                placeholder="+63 912 345 6789"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Organization / Tenant Name</label>
            <input
              v-model="account.company_name"
              type="text"
              placeholder="My ISP Company"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
            <p class="mt-1 text-xs text-gray-500">This is your organization name displayed across the platform</p>
          </div>
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="accountSaving"
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ accountSaving ? 'Saving...' : 'Save Profile' }}
            </button>
          </div>
        </form>
      </div>

      <!-- Change Password -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Change Password</h2>

        <div
          v-if="passwordMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            passwordMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ passwordMsg }}
        </div>

        <form @submit.prevent="handleChangePassword" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Current Password</label>
            <input
              v-model="currentPassword"
              type="password"
              placeholder="Enter current password"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
              <input
                v-model="newPassword"
                type="password"
                placeholder="Enter new password"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
              <input
                v-model="confirmPassword"
                type="password"
                placeholder="Confirm new password"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
          </div>
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="passwordSaving"
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ passwordSaving ? 'Changing...' : 'Change Password' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- SMTP Tab -->
    <!-- Billing Tab -->
    <div v-if="activeTab === 'billing'" class="space-y-6">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Billing Enforcement</h2>
        <p class="text-sm text-gray-500 mb-4">Configure grace periods for overdue invoices. The system automatically throttles and disconnects customers based on these settings.</p>

        <div v-if="billingMsg" :class="['mb-4 rounded-lg px-4 py-3 text-sm', billingMsgType === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200']">
          {{ billingMsg }}
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Default Due Day (1-28)</label>
            <select v-model="billing.billing_default_due_day" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors">
              <option v-for="d in 28" :key="d" :value="String(d)">{{ d }}</option>
            </select>
            <p class="text-xs text-gray-400 mt-1">Default for new customers (can be overridden per customer)</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Reminder Days Before Due</label>
            <input v-model="billing.billing_reminder_days_before_due" type="number" min="1" max="30" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
            <p class="text-xs text-gray-400 mt-1">Send SMS/email reminder this many days before due date</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Throttle After (days overdue)</label>
            <input v-model="billing.billing_throttle_days_after_due" type="number" min="1" max="30" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
            <p class="text-xs text-gray-400 mt-1">Reduce speed to 1Mbps after this many days overdue</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Disconnect After (days overdue)</label>
            <input v-model="billing.billing_disconnect_days_after_due" type="number" min="1" max="60" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
            <p class="text-xs text-gray-400 mt-1">Disable PPPoE secret after this many days overdue</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Terminate After (days overdue)</label>
            <input v-model="billing.billing_terminate_days_after_due" type="number" min="7" max="365" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
            <p class="text-xs text-gray-400 mt-1">Flag for permanent removal after this many days overdue</p>
          </div>
        </div>
      </div>

      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Invoice Notifications</h2>
        <div class="space-y-3">
          <label class="flex items-center gap-3">
            <input type="checkbox" :checked="billing.billing_send_invoice_email === 'true'" @change="billing.billing_send_invoice_email = ($event.target as HTMLInputElement).checked ? 'true' : 'false'" class="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary/30" />
            <span class="text-sm text-gray-700">Send invoice via <strong>email</strong> when generated</span>
          </label>
          <label class="flex items-center gap-3">
            <input type="checkbox" :checked="billing.billing_send_invoice_sms === 'true'" @change="billing.billing_send_invoice_sms = ($event.target as HTMLInputElement).checked ? 'true' : 'false'" class="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary/30" />
            <span class="text-sm text-gray-700">Send invoice via <strong>SMS</strong> when generated (requires SMS configured)</span>
          </label>
        </div>
      </div>

      <div class="flex justify-end">
        <button
          @click="handleSaveBilling"
          :disabled="billingSaving"
          class="px-6 py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ billingSaving ? 'Saving...' : 'Save Billing Settings' }}
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'smtp'" class="space-y-6">
      <!-- SMTP Settings Form -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">SMTP Configuration</h2>

        <!-- Message -->
        <div
          v-if="smtpMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            smtpMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ smtpMsg }}
        </div>

        <div v-if="smtpLoading" class="space-y-4">
          <div v-for="i in 6" :key="i" class="h-10 bg-gray-100 rounded-lg animate-pulse" />
        </div>

        <form v-else @submit.prevent="handleSaveSmtp" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">SMTP Host</label>
              <input
                v-model="smtp.smtp_host"
                type="text"
                placeholder="smtp.gmail.com"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">SMTP Port</label>
              <input
                v-model.number="smtp.smtp_port"
                type="number"
                placeholder="587"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">SMTP User</label>
              <input
                v-model="smtp.smtp_user"
                type="text"
                placeholder="user@example.com"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">SMTP Password</label>
              <input
                v-model="smtp.smtp_password"
                type="password"
                placeholder="••••••••"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">From Email</label>
              <input
                v-model="smtp.smtp_from"
                type="email"
                placeholder="noreply@example.com"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">From Name</label>
              <input
                v-model="smtp.smtp_from_name"
                type="text"
                placeholder="NetLedger"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
          </div>
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="smtpSaving"
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ smtpSaving ? 'Saving...' : 'Save SMTP Settings' }}
            </button>
          </div>
        </form>
      </div>

      <!-- Test Email -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Send Test Email</h2>

        <div
          v-if="smtpTestMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            smtpTestMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ smtpTestMsg }}
        </div>

        <div class="flex items-end gap-3">
          <div class="flex-1">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Recipient Email</label>
            <input
              v-model="testEmail"
              type="email"
              placeholder="test@example.com"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <button
            @click="handleTestSmtp"
            :disabled="smtpTesting || !testEmail"
            class="px-4 py-2 text-sm font-medium text-primary bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors disabled:opacity-50"
          >
            {{ smtpTesting ? 'Sending...' : 'Send Test' }}
          </button>
        </div>
      </div>
    </div>

    <!-- SMS Tab -->
    <div v-if="activeTab === 'sms'" class="space-y-6">
      <!-- SMS Settings Form -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">SMS Configuration</h2>

        <div
          v-if="smsMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            smsMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ smsMsg }}
        </div>

        <div v-if="smsLoading" class="space-y-4">
          <div v-for="i in 3" :key="i" class="h-10 bg-gray-100 rounded-lg animate-pulse" />
        </div>

        <form v-else @submit.prevent="handleSaveSms" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">SMS Provider</label>
            <input
              v-model="sms.sms_provider"
              type="text"
              placeholder="twilio, semaphore, etc."
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">API Key</label>
            <input
              v-model="sms.sms_api_key"
              type="password"
              placeholder="••••••••"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Sender Name</label>
            <input
              v-model="sms.sms_sender_name"
              type="text"
              placeholder="NetLedger"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="smsSaving"
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ smsSaving ? 'Saving...' : 'Save SMS Settings' }}
            </button>
          </div>
        </form>
      </div>

      <!-- Test SMS -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Send Test SMS</h2>

        <div
          v-if="smsTestMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            smsTestMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ smsTestMsg }}
        </div>

        <div class="flex items-end gap-3">
          <div class="flex-1">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Recipient Number</label>
            <input
              v-model="testNumber"
              type="text"
              placeholder="+639XXXXXXXXX"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <button
            @click="handleTestSms"
            :disabled="smsTesting || !testNumber"
            class="px-4 py-2 text-sm font-medium text-primary bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors disabled:opacity-50"
          >
            {{ smsTesting ? 'Sending...' : 'Send Test' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Branding Tab -->
    <div v-if="activeTab === 'branding'" class="space-y-6">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-4">Company Profile / Invoice Branding</h2>

        <div
          v-if="brandingMsg"
          :class="[
            'mb-4 rounded-lg px-4 py-3 text-sm border',
            brandingMsgType === 'success'
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          ]"
        >
          {{ brandingMsg }}
        </div>

        <div v-if="brandingLoading" class="space-y-4">
          <div v-for="i in 7" :key="i" class="h-10 bg-gray-100 rounded-lg animate-pulse" />
        </div>

        <form v-else @submit.prevent="handleSaveBranding" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Company Name</label>
              <input
                v-model="branding.company_name"
                type="text"
                placeholder="My ISP Company"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Company Phone</label>
              <input
                v-model="branding.company_phone"
                type="text"
                placeholder="+63 912 345 6789"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Company Email</label>
              <input
                v-model="branding.company_email"
                type="email"
                placeholder="billing@myisp.com"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1.5">Invoice Number Prefix</label>
              <input
                v-model="branding.invoice_prefix"
                type="text"
                placeholder="INV-"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Company Address</label>
            <textarea
              v-model="branding.company_address"
              rows="2"
              placeholder="123 Main St, Barangay, City, Province"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Company Logo</label>
            <div class="flex items-center gap-4">
              <div v-if="branding.company_logo_url" class="w-16 h-16 rounded-lg border border-gray-200 bg-gray-50 flex items-center justify-center overflow-hidden">
                <img :src="branding.company_logo_url" class="max-w-full max-h-full object-contain" />
              </div>
              <div v-else class="w-16 h-16 rounded-lg border-2 border-dashed border-gray-300 bg-gray-50 flex items-center justify-center">
                <svg class="w-6 h-6 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/></svg>
              </div>
              <div class="flex-1">
                <label class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary bg-primary/5 border border-primary/20 rounded-lg hover:bg-primary/10 cursor-pointer transition-colors">
                  <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z"/><path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z"/></svg>
                  Browse Logo
                  <input type="file" accept="image/*" class="hidden" @change="handleLogoUpload" />
                </label>
                <p class="mt-1 text-xs text-gray-500">PNG, JPG or SVG. Will appear on invoice PDFs.</p>
                <p v-if="logoUploading" class="mt-1 text-xs text-primary">Uploading...</p>
              </div>
            </div>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Invoice Footer Text</label>
            <textarea
              v-model="branding.invoice_footer"
              rows="2"
              placeholder="Thank you for your business!"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
            />
          </div>
          <!-- Customer Portal Link -->
          <div v-if="portalUrl" class="rounded-lg bg-blue-50 border border-blue-200 p-4">
            <label class="block text-sm font-medium text-blue-800 mb-1.5">Customer Portal Link</label>
            <div class="flex items-center gap-2">
              <code class="flex-1 px-3 py-2 bg-white rounded-lg border border-blue-200 text-sm font-mono text-blue-700 select-all">{{ portalUrl }}</code>
              <button type="button" @click="copyPortalUrl" class="px-3 py-2 text-xs font-medium text-blue-700 bg-blue-100 hover:bg-blue-200 rounded-lg transition-colors">Copy</button>
            </div>
            <p class="mt-1.5 text-xs text-blue-600">Share this link with your customers. They can log in using their PPPoE username and password.</p>
          </div>
          <div v-else class="rounded-lg bg-gray-50 border border-gray-200 p-4">
            <p class="text-sm text-gray-500">Save your company name to generate a Customer Portal link for your subscribers.</p>
          </div>
          <div class="flex justify-end">
            <button
              type="submit"
              :disabled="brandingSaving"
              class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ brandingSaving ? 'Saving...' : 'Save Branding Settings' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Notifications Tab -->
    <div v-if="activeTab === 'notifications'" class="space-y-6">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-2">Notification Templates</h2>
        <p class="text-sm text-gray-500 mb-4">Customize the messages sent to your customers. Use placeholders like <code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono text-primary">{customer_name}</code> that will be replaced with actual values.</p>

        <!-- Available variables -->
        <div class="mb-6 rounded-lg bg-gray-50 border border-gray-200 px-4 py-3">
          <p class="text-xs font-medium text-gray-600 mb-2">Available Variables:</p>
          <div class="flex flex-wrap gap-2">
            <code v-for="v in ['{customer_name}', '{amount}', '{plan_name}', '{due_date}', '{due_date_short}', '{portal_url}']" :key="v" class="bg-white border border-gray-200 px-2 py-1 rounded text-xs font-mono text-gray-700">{{ v }}</code>
          </div>
        </div>

        <div
          v-if="templatesMsg"
          :class="['mb-4 rounded-lg px-4 py-3 text-sm border', templatesMsgType === 'success' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700']"
        >{{ templatesMsg }}</div>

        <div class="space-y-6">
          <!-- Invoice Email -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>
              Invoice Email
            </h3>
            <div class="space-y-3">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Subject</label>
                <input v-model="templates.tpl_invoice_email_subject" type="text" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Body</label>
                <textarea v-model="templates.tpl_invoice_email_body" rows="5" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
              </div>
            </div>
          </div>

          <!-- Invoice SMS -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" /></svg>
              Invoice SMS
            </h3>
            <textarea v-model="templates.tpl_invoice_sms" rows="2" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
            <p class="text-xs text-gray-400 mt-1">Keep SMS under 160 characters when possible</p>
          </div>

          <!-- Reminder SMS -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>
              Payment Reminder SMS
            </h3>
            <textarea v-model="templates.tpl_reminder_sms" rows="2" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
          </div>

          <!-- Overdue Email -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
              Overdue Notice Email
            </h3>
            <div class="space-y-3">
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Subject</label>
                <input v-model="templates.tpl_overdue_email_subject" type="text" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-600 mb-1">Body</label>
                <textarea v-model="templates.tpl_overdue_email_body" rows="5" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
              </div>
            </div>
          </div>

          <!-- Overdue SMS -->
          <div>
            <h3 class="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <svg class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
              Overdue Notice SMS
            </h3>
            <textarea v-model="templates.tpl_overdue_sms" rows="2" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary font-mono" />
          </div>
        </div>

        <!-- Save button -->
        <div class="flex justify-end mt-6">
          <button
            @click="handleSaveTemplates"
            :disabled="templatesSaving"
            class="px-6 py-2.5 rounded-lg bg-primary text-white font-medium text-sm hover:bg-primary-hover disabled:opacity-60 transition-colors"
          >
            {{ templatesSaving ? 'Saving...' : 'Save Templates' }}
          </button>
        </div>
      </div>
    </div>

    <!-- LibreQoS Tab -->
    <div v-if="activeTab === 'libreqos'" class="space-y-6">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <h2 class="text-lg font-semibold text-gray-800 mb-2">LibreQoS Integration</h2>
        <p class="text-sm text-gray-500 mb-6">Connect NetLedger to your LibreQoS traffic shaper. NetLedger provides a CSV endpoint that LibreQoS pulls on a schedule to sync subscriber speed limits.</p>

        <div v-if="libreqosLoading" class="space-y-4">
          <div class="h-4 w-48 bg-gray-100 rounded animate-pulse" />
          <div class="h-10 w-full bg-gray-100 rounded animate-pulse" />
        </div>

        <div v-else class="space-y-5">
          <!-- Token -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">API Token</label>
            <div class="flex gap-2">
              <input
                :value="libreqosToken || 'No token generated yet'"
                type="text"
                readonly
                class="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono bg-gray-50 text-gray-600"
              />
              <button
                @click="generateLibreqosToken"
                :disabled="libreqosGenerating"
                class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50 whitespace-nowrap"
              >
                {{ libreqosGenerating ? 'Generating...' : libreqosToken ? 'Regenerate' : 'Generate Token' }}
              </button>
            </div>
          </div>

          <!-- URL -->
          <div v-if="libreqosToken">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">ShapedDevices.csv URL</label>
            <div class="flex gap-2">
              <input
                :value="libreqosUrl"
                type="text"
                readonly
                class="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono bg-gray-50 text-gray-600"
              />
              <button
                @click="copyLibreqosUrl"
                class="px-4 py-2 text-sm font-medium rounded-lg border transition-colors whitespace-nowrap"
                :class="libreqosCopied ? 'text-green-700 bg-green-50 border-green-300' : 'text-gray-700 bg-white border-gray-300 hover:bg-gray-50'"
              >
                {{ libreqosCopied ? 'Copied!' : 'Copy URL' }}
              </button>
            </div>
          </div>

          <!-- Setup Instructions -->
          <div v-if="libreqosToken" class="border-t border-gray-100 pt-5 mt-5">
            <h3 class="text-sm font-semibold text-gray-800 mb-3">Setup on your LibreQoS server</h3>
            <p class="text-sm text-gray-500 mb-3">Add this cron job to your LibreQoS server to pull subscriber data every 5 minutes:</p>
            <div class="rounded-lg bg-gray-900 p-4 overflow-x-auto">
              <code class="text-sm font-mono text-green-400">*/5 * * * * curl -s "{{ libreqosUrl }}" > /opt/libreqos/src/ShapedDevices.csv && cd /opt/libreqos/src && sudo ./LibreQoS.py</code>
            </div>
            <div class="mt-4 space-y-2 text-sm text-gray-500">
              <p><strong class="text-gray-700">How it works:</strong></p>
              <ul class="list-disc list-inside space-y-1 ml-2">
                <li>NetLedger queries your MikroTik for active PPPoE sessions (gets customer IPs)</li>
                <li>Generates a CSV mapping each online customer to their plan speeds</li>
                <li>LibreQoS reads the CSV and applies per-subscriber fair queueing</li>
                <li>Offline customers are excluded (no IP = no shaping needed)</li>
                <li>Min speed is set to 30% of max for fair bandwidth distribution</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
