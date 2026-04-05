<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  getProfile,
  updateProfile,
  type SmtpSettings,
  type SmsSettings,
  type BrandingSettings,
  type ProfileUpdate,
} from '../api/settings'

const activeTab = ref<'account' | 'smtp' | 'sms' | 'branding'>('account')

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
})
const brandingLoading = ref(false)
const brandingSaving = ref(false)
const brandingMsg = ref('')
const brandingMsgType = ref<'success' | 'error'>('success')
const logoUploading = ref(false)

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
    brandingMsg.value = 'Branding settings saved successfully'
    brandingMsgType.value = 'success'
  } catch (e: any) {
    brandingMsg.value = e.response?.data?.detail || 'Failed to save branding settings'
    brandingMsgType.value = 'error'
  } finally {
    brandingSaving.value = false
  }
}

onMounted(() => {
  loadAccount()
  loadSmtp()
  loadSms()
  loadBranding()
})
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Settings</h1>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-gray-200">
      <button
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
  </div>
</template>
