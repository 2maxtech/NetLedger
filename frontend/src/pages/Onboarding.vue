<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { isSaaS } from '../composables/useDeploymentMode'
import { createRouter as apiCreateRouter, getRouterStatus, importPreview, importFromRouter, vpnSetup, vpnActivate, type RouterType, type ImportPreview, type VpnSetupResponse } from '../api/routers'
import { createPlan, type Plan } from '../api/plans'
import { createCustomer } from '../api/customers'
import { saveBillingSettings } from '../api/settings'
import { dismissOnboarding, getOnboardingStatus } from '../api/onboarding'

const router = useRouter()
const step = ref(1)
const loading = ref(false)
const error = ref('')

// --- Step 1: Router ---
const routerCreated = ref<RouterType | null>(null)
const routerForm = reactive({
  name: '',
  url: '',
  username: 'admin',
  password: '',
})
const routerConnected = ref(false)

// VPN substep (SaaS)
const vpnStep = ref(0) // 0=not started, 1=copy script, 2=paste key, 3=connected
const vpnData = ref<VpnSetupResponse | null>(null)
const vpnClientKey = ref('')
const vpnCopied = ref(false)

// --- Step 2: Import ---
const previewData = ref<ImportPreview | null>(null)
const planPrices = reactive<Record<string, number>>({})
const importResult = ref<{ customers_created: number; plans_created: number } | null>(null)

// Manual mode (no router)
const manualPlan = reactive({ name: '', download_mbps: 10, upload_mbps: 5, monthly_price: 999 })
const manualCustomer = reactive({ full_name: '', pppoe_username: '', pppoe_password: '' })
const manualPlanCreated = ref<Plan | null>(null)
const manualCustomerCreated = ref(false)

// --- Step 3: Billing ---
const billing = reactive({
  billing_default_due_day: '15',
  billing_throttle_days_after_due: '3',
  billing_disconnect_days_after_due: '5',
})
const billingSaved = ref(false)

// --- Step 4: Summary ---
const summary = reactive({
  routerName: '',
  customerCount: 0,
  planCount: 0,
  dueDay: 15,
  throttleDays: 3,
  disconnectDays: 5,
})

const stepLabels = ['Connect Router', 'Customers', 'Billing', 'Ready']

// ========================
// Step 1: Router
// ========================

async function createAndTestRouter() {
  error.value = ''
  loading.value = true
  try {
    if (isSaaS) {
      // SaaS: create router with placeholder URL, then start VPN setup
      const { data } = await apiCreateRouter({
        name: routerForm.name || 'My Router',
        url: 'http://pending-vpn',
        username: routerForm.username,
        password: routerForm.password,
      })
      routerCreated.value = data
      // Start VPN setup
      vpnStep.value = 1
      const { data: vpn } = await vpnSetup(data.id)
      vpnData.value = vpn
    } else {
      // Self-hosted: create router with direct LAN connection
      const { data } = await apiCreateRouter({
        name: routerForm.name || 'My Router',
        url: routerForm.url,
        username: routerForm.username,
        password: routerForm.password,
      })
      routerCreated.value = data
      // Test connection
      const { data: status } = await getRouterStatus(data.id)
      if (status.connected) {
        routerConnected.value = true
        summary.routerName = routerForm.name || 'My Router'
      } else {
        error.value = status.error || 'Could not connect to router. Check IP and credentials.'
      }
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create router'
  } finally {
    loading.value = false
  }
}

function copyVpnScript() {
  if (vpnData.value?.script) {
    navigator.clipboard.writeText(vpnData.value.script)
    vpnCopied.value = true
    setTimeout(() => vpnCopied.value = false, 2000)
  }
}

async function activateVpn() {
  if (!vpnClientKey.value.trim()) {
    error.value = 'Please paste the MikroTik public key'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await vpnActivate(routerCreated.value!.id, { public_key: vpnClientKey.value.trim() })
    vpnStep.value = 3
    routerConnected.value = true
    summary.routerName = routerForm.name || 'My Router'
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to activate VPN'
  } finally {
    loading.value = false
  }
}

// ========================
// Step 2: Import
// ========================

async function loadImportPreview(retries = 3) {
  if (!routerCreated.value) return
  error.value = ''
  loading.value = true
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const { data } = await importPreview(routerCreated.value.id)
      previewData.value = data
      for (const p of data.plans) {
        planPrices[p.name] = p.current_price || 0
      }
      loading.value = false
      return
    } catch (e: any) {
      if (attempt < retries - 1) {
        // VPN tunnel may need time to establish — wait and retry
        await new Promise(r => setTimeout(r, 3000))
      } else {
        error.value = e.response?.data?.detail || 'Could not reach router. The VPN tunnel may still be connecting — try clicking "Retry" below.'
      }
    }
  }
  loading.value = false
}

const importRetrying = ref(false)
async function retryImport() {
  importRetrying.value = true
  error.value = ''
  await loadImportPreview(2)
  importRetrying.value = false
}

async function doImport() {
  if (!routerCreated.value) return
  error.value = ''
  loading.value = true
  try {
    const { data } = await importFromRouter(routerCreated.value.id, planPrices)
    importResult.value = data
    summary.customerCount = data.customers_created
    summary.planCount = data.plans_created
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Import failed'
  } finally {
    loading.value = false
  }
}

async function createManualPlan() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await createPlan({
      name: manualPlan.name,
      download_mbps: manualPlan.download_mbps,
      upload_mbps: manualPlan.upload_mbps,
      monthly_price: manualPlan.monthly_price,
      is_active: true,
    })
    manualPlanCreated.value = data
    summary.planCount = 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create plan'
  } finally {
    loading.value = false
  }
}

async function createManualCustomer() {
  if (!manualPlanCreated.value) {
    error.value = 'Create a plan first'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await createCustomer({
      full_name: manualCustomer.full_name,
      pppoe_username: manualCustomer.pppoe_username,
      pppoe_password: manualCustomer.pppoe_password,
      plan_id: manualPlanCreated.value.id,
    })
    manualCustomerCreated.value = true
    summary.customerCount = 1
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to create customer'
  } finally {
    loading.value = false
  }
}

// ========================
// Step 3: Billing
// ========================

async function saveBilling() {
  error.value = ''
  loading.value = true
  try {
    await saveBillingSettings(billing)
    billingSaved.value = true
    summary.dueDay = parseInt(billing.billing_default_due_day)
    summary.throttleDays = parseInt(billing.billing_throttle_days_after_due)
    summary.disconnectDays = parseInt(billing.billing_disconnect_days_after_due)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to save billing settings'
  } finally {
    loading.value = false
  }
}

// ========================
// Navigation
// ========================

function nextStep() {
  error.value = ''
  if (step.value === 2 && !routerConnected.value && !importResult.value && !manualPlanCreated.value) {
    // Skipping step 2 with nothing done — that's fine
  }
  if (step.value < 4) {
    step.value++
    // Auto-load import preview when entering step 2 with a connected router
    if (step.value === 2 && routerConnected.value && !previewData.value) {
      loadImportPreview()
    }
  }
}

function skipStep() {
  error.value = ''
  // Save defaults when skipping billing
  if (step.value === 3 && !billingSaved.value) {
    saveBillingSettings(billing).catch(() => {})
    summary.dueDay = parseInt(billing.billing_default_due_day)
    summary.throttleDays = parseInt(billing.billing_throttle_days_after_due)
    summary.disconnectDays = parseInt(billing.billing_disconnect_days_after_due)
  }
  step.value++
}

async function finish() {
  loading.value = true
  try {
    await dismissOnboarding()
    router.push('/dashboard')
  } catch {
    router.push('/dashboard')
  }
}

function exitWizard() {
  router.push('/dashboard')
}

onMounted(async () => {
  try {
    const { data } = await getOnboardingStatus()
    if (data.dismissed || data.completed >= data.total) {
      router.replace('/dashboard')
    }
  } catch { /* continue */ }
})
</script>

<template>
  <div class="min-h-screen bg-gray-950 text-gray-100">
    <!-- Header -->
    <div class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
      <div class="flex items-center gap-3">
        <img src="/logo-2.png" class="w-8 h-8" alt="NetLedger" />
        <span class="text-lg font-bold text-white">NetLedger Setup</span>
      </div>
      <button @click="exitWizard" class="text-gray-400 hover:text-white text-sm">
        Exit to Dashboard
      </button>
    </div>

    <!-- Step indicator -->
    <div class="max-w-2xl mx-auto px-6 pt-8">
      <div class="flex items-center justify-between mb-8">
        <template v-for="(label, i) in stepLabels" :key="i">
          <div class="flex items-center gap-2">
            <div :class="[
              'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all',
              step > i + 1 ? 'bg-green-500 text-white' :
              step === i + 1 ? 'bg-primary text-white' :
              'bg-gray-800 text-gray-500'
            ]">
              <svg v-if="step > i + 1" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <span :class="['text-sm hidden sm:inline', step === i + 1 ? 'text-white font-medium' : 'text-gray-500']">{{ label }}</span>
          </div>
          <div v-if="i < 3" :class="['flex-1 h-px mx-2', step > i + 1 ? 'bg-green-500' : 'bg-gray-800']" />
        </template>
      </div>
    </div>

    <!-- Content -->
    <div class="max-w-2xl mx-auto px-6 pb-12">
      <!-- Error -->
      <div v-if="error" class="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
        {{ error }}
      </div>

      <!-- ==================== STEP 1: Router ==================== -->
      <div v-if="step === 1">
        <h2 class="text-2xl font-bold text-white mb-2">Connect Your Router</h2>
        <p class="text-gray-400 mb-6">Link your MikroTik router so NetLedger can manage PPPoE accounts and bandwidth.</p>

        <!-- Not yet connected -->
        <div v-if="!routerConnected && vpnStep === 0" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Router Name</label>
            <input v-model="routerForm.name" type="text" placeholder="e.g. Main Router" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-primary focus:outline-none" />
          </div>

          <!-- Router credentials (both SaaS and self-hosted need these) -->
          <template v-if="!isSaaS">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Router URL</label>
              <input v-model="routerForm.url" type="text" placeholder="http://192.168.88.1" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-primary focus:outline-none" />
            </div>
          </template>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Router Username</label>
              <input v-model="routerForm.username" type="text" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-primary focus:outline-none" />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-300 mb-1">Router Password</label>
              <input v-model="routerForm.password" type="password" placeholder="MikroTik admin password" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-primary focus:outline-none" />
            </div>
          </div>

          <button @click="createAndTestRouter" :disabled="loading || (!isSaaS && !routerForm.url) || !routerForm.password" class="w-full py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors disabled:opacity-50">
            {{ loading ? 'Connecting...' : (isSaaS ? 'Connect via VPN' : 'Test Connection') }}
          </button>
        </div>

        <!-- VPN Step 1: Copy script -->
        <div v-if="vpnStep === 1 && vpnData" class="space-y-4">
          <div class="p-4 rounded-lg bg-gray-800 border border-gray-700">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm font-medium text-gray-300">1. Run this script on your MikroTik terminal</span>
              <button @click="copyVpnScript" class="px-3 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20">
                {{ vpnCopied ? 'Copied!' : 'Copy' }}
              </button>
            </div>
            <pre class="text-xs text-green-400 bg-gray-900 p-3 rounded overflow-x-auto whitespace-pre-wrap break-all">{{ vpnData.script }}</pre>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">2. Paste the MikroTik public key shown after running the script</label>
            <input v-model="vpnClientKey" type="text" placeholder="Paste public key here..." class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono text-sm" />
          </div>
          <button @click="activateVpn" :disabled="loading || !vpnClientKey.trim()" class="w-full py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors disabled:opacity-50">
            {{ loading ? 'Activating...' : 'Activate VPN' }}
          </button>
        </div>

        <!-- VPN Step 3 / Direct connection: Connected -->
        <div v-if="routerConnected" class="p-6 rounded-xl bg-green-500/10 border border-green-500/20 text-center">
          <svg class="w-12 h-12 text-green-500 mx-auto mb-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
          <p class="text-lg font-semibold text-green-400">Router Connected!</p>
          <p class="text-sm text-gray-400 mt-1">{{ summary.routerName }}</p>
          <button @click="nextStep" class="mt-4 px-8 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors">
            Continue
          </button>
        </div>

        <!-- Skip -->
        <div v-if="!routerConnected" class="mt-6 text-center">
          <button @click="skipStep" class="text-sm text-gray-500 hover:text-gray-300">I'll set this up later</button>
        </div>
      </div>

      <!-- ==================== STEP 2: Customers ==================== -->
      <div v-if="step === 2">
        <h2 class="text-2xl font-bold text-white mb-2">Add Your Customers</h2>
        <p class="text-gray-400 mb-6">
          {{ routerConnected ? 'Import existing PPPoE accounts from your router, or add them manually later.' : 'Create your first plan and customer to get started.' }}
        </p>

        <!-- Import from router -->
        <div v-if="routerConnected && !importResult">
          <!-- Loading preview -->
          <div v-if="loading && !previewData" class="text-center py-8 text-gray-400">
            Loading customers from router... (this may take a moment if the VPN just connected)
          </div>

          <!-- Retry button on error -->
          <div v-if="error && !previewData && !loading" class="text-center py-4">
            <button @click="retryImport" :disabled="importRetrying" class="px-6 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors disabled:opacity-50">
              {{ importRetrying ? 'Retrying...' : 'Retry Connection' }}
            </button>
          </div>

          <!-- Preview table -->
          <div v-if="previewData" class="space-y-4">
            <div class="rounded-lg border border-gray-700 overflow-hidden">
              <div class="p-3 bg-gray-800/50 text-sm text-gray-300 font-medium">
                Found {{ previewData.new_customers }} new customers in {{ previewData.plans.length }} plan(s)
              </div>
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-800">
                    <th class="text-left p-3 text-gray-400 font-medium">Plan</th>
                    <th class="text-left p-3 text-gray-400 font-medium">Speed</th>
                    <th class="text-left p-3 text-gray-400 font-medium">Customers</th>
                    <th class="text-left p-3 text-gray-400 font-medium">Monthly Price</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="plan in previewData.plans" :key="plan.name" class="border-b border-gray-800/50">
                    <td class="p-3 text-white">{{ plan.name }}</td>
                    <td class="p-3 text-gray-400">{{ plan.rate_limit || 'No limit' }}</td>
                    <td class="p-3 text-gray-400">{{ plan.customer_count }}</td>
                    <td class="p-3">
                      <div class="flex items-center gap-1">
                        <span class="text-gray-500">&#8369;</span>
                        <input v-model.number="planPrices[plan.name]" type="number" min="0" class="w-24 px-2 py-1 rounded bg-gray-800 border border-gray-700 text-white text-sm focus:border-primary focus:outline-none" />
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <button @click="doImport" :disabled="loading" class="w-full py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors disabled:opacity-50">
              {{ loading ? 'Importing...' : `Import ${previewData.new_customers} Customers` }}
            </button>
          </div>
        </div>

        <!-- Import result -->
        <div v-if="importResult" class="p-6 rounded-xl bg-green-500/10 border border-green-500/20 text-center">
          <svg class="w-12 h-12 text-green-500 mx-auto mb-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
          <p class="text-lg font-semibold text-green-400">Import Complete!</p>
          <p class="text-sm text-gray-400 mt-1">{{ importResult.customers_created }} customers, {{ importResult.plans_created }} plans created</p>
          <button @click="nextStep" class="mt-4 px-8 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors">
            Continue
          </button>
        </div>

        <!-- Manual mode (no router) -->
        <div v-if="!routerConnected && !importResult" class="space-y-6">
          <!-- Create plan -->
          <div class="rounded-xl border border-gray-700 p-5">
            <h3 class="font-semibold text-white mb-3">Create a Plan</h3>
            <div class="grid grid-cols-2 gap-3">
              <div class="col-span-2">
                <input v-model="manualPlan.name" type="text" placeholder="Plan name (e.g. Basic 10Mbps)" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-primary focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500">Download (Mbps)</label>
                <input v-model.number="manualPlan.download_mbps" type="number" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-primary focus:outline-none" />
              </div>
              <div>
                <label class="text-xs text-gray-500">Upload (Mbps)</label>
                <input v-model.number="manualPlan.upload_mbps" type="number" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-primary focus:outline-none" />
              </div>
              <div class="col-span-2">
                <label class="text-xs text-gray-500">Monthly Price (&#8369;)</label>
                <input v-model.number="manualPlan.monthly_price" type="number" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm focus:border-primary focus:outline-none" />
              </div>
            </div>
            <button v-if="!manualPlanCreated" @click="createManualPlan" :disabled="loading || !manualPlan.name" class="mt-3 w-full py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium text-sm transition-colors disabled:opacity-50">
              {{ loading ? 'Creating...' : 'Create Plan' }}
            </button>
            <div v-else class="mt-3 text-sm text-green-400 flex items-center gap-1">
              <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              Plan "{{ manualPlanCreated.name }}" created
            </div>
          </div>

          <!-- Create customer (only after plan) -->
          <div v-if="manualPlanCreated" class="rounded-xl border border-gray-700 p-5">
            <h3 class="font-semibold text-white mb-3">Add a Customer (optional)</h3>
            <div class="space-y-3">
              <input v-model="manualCustomer.full_name" type="text" placeholder="Full name" class="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-primary focus:outline-none" />
              <div class="grid grid-cols-2 gap-3">
                <input v-model="manualCustomer.pppoe_username" type="text" placeholder="PPPoE username" class="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-primary focus:outline-none" />
                <input v-model="manualCustomer.pppoe_password" type="text" placeholder="PPPoE password" class="px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-white placeholder-gray-500 text-sm focus:border-primary focus:outline-none" />
              </div>
            </div>
            <button v-if="!manualCustomerCreated" @click="createManualCustomer" :disabled="loading || !manualCustomer.full_name || !manualCustomer.pppoe_username" class="mt-3 w-full py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium text-sm transition-colors disabled:opacity-50">
              {{ loading ? 'Creating...' : 'Add Customer' }}
            </button>
            <div v-else class="mt-3 text-sm text-green-400 flex items-center gap-1">
              <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              Customer added
            </div>
          </div>
        </div>

        <!-- Next / Skip -->
        <div class="mt-6 flex items-center justify-between">
          <button @click="skipStep" class="text-sm text-gray-500 hover:text-gray-300">I'll do this later</button>
          <button v-if="importResult || manualPlanCreated" @click="nextStep" class="px-6 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors">
            Continue
          </button>
        </div>
      </div>

      <!-- ==================== STEP 3: Billing ==================== -->
      <div v-if="step === 3">
        <h2 class="text-2xl font-bold text-white mb-2">Billing Settings</h2>
        <p class="text-gray-400 mb-6">Set your billing rules. You can change these anytime in Settings.</p>

        <div v-if="!billingSaved" class="rounded-xl border border-gray-700 p-5 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Default Due Day (of the month)</label>
            <select v-model="billing.billing_default_due_day" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-primary focus:outline-none">
              <option v-for="d in 28" :key="d" :value="String(d)">{{ d }}</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Days overdue before throttle</label>
            <input v-model="billing.billing_throttle_days_after_due" type="number" min="1" max="30" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-primary focus:outline-none" />
            <p class="text-xs text-gray-500 mt-1">Customer speed will be reduced after this many days past due</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">Days overdue before disconnect</label>
            <input v-model="billing.billing_disconnect_days_after_due" type="number" min="1" max="60" class="w-full px-4 py-2.5 rounded-lg bg-gray-800 border border-gray-700 text-white focus:border-primary focus:outline-none" />
            <p class="text-xs text-gray-500 mt-1">Customer will be fully disconnected after this many days past due</p>
          </div>
          <div class="flex gap-3">
            <button @click="saveBilling" :disabled="loading" class="flex-1 py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors disabled:opacity-50">
              {{ loading ? 'Saving...' : 'Save Settings' }}
            </button>
            <button @click="skipStep" class="px-6 py-3 rounded-xl border border-gray-700 text-gray-400 hover:text-white hover:border-gray-500 font-medium transition-colors">
              Use Defaults
            </button>
          </div>
        </div>

        <div v-if="billingSaved" class="p-6 rounded-xl bg-green-500/10 border border-green-500/20 text-center">
          <svg class="w-12 h-12 text-green-500 mx-auto mb-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
          <p class="text-lg font-semibold text-green-400">Billing Configured!</p>
          <button @click="nextStep" class="mt-4 px-8 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white font-semibold transition-colors">
            Continue
          </button>
        </div>
      </div>

      <!-- ==================== STEP 4: Ready ==================== -->
      <div v-if="step === 4">
        <h2 class="text-2xl font-bold text-white mb-2">You're All Set!</h2>
        <p class="text-gray-400 mb-6">Here's a summary of your setup. You can change everything from the dashboard.</p>

        <div class="rounded-xl border border-gray-700 p-5 space-y-3">
          <div class="flex items-center justify-between py-2">
            <span class="text-gray-400">Router</span>
            <span :class="summary.routerName ? 'text-green-400' : 'text-gray-500'">
              {{ summary.routerName || 'Not configured' }}
            </span>
          </div>
          <div class="border-t border-gray-800" />
          <div class="flex items-center justify-between py-2">
            <span class="text-gray-400">Customers</span>
            <span :class="summary.customerCount > 0 ? 'text-green-400' : 'text-gray-500'">
              {{ summary.customerCount > 0 ? `${summary.customerCount} imported` : 'None yet' }}
            </span>
          </div>
          <div class="border-t border-gray-800" />
          <div class="flex items-center justify-between py-2">
            <span class="text-gray-400">Plans</span>
            <span :class="summary.planCount > 0 ? 'text-green-400' : 'text-gray-500'">
              {{ summary.planCount > 0 ? `${summary.planCount} plan(s)` : 'None yet' }}
            </span>
          </div>
          <div class="border-t border-gray-800" />
          <div class="flex items-center justify-between py-2">
            <span class="text-gray-400">Billing</span>
            <span class="text-green-400">
              Due day {{ summary.dueDay }}, throttle {{ summary.throttleDays }}d, disconnect {{ summary.disconnectDays }}d
            </span>
          </div>
        </div>

        <button @click="finish" :disabled="loading" class="mt-6 w-full py-3 rounded-xl bg-primary hover:bg-primary-hover text-white font-bold text-lg transition-colors disabled:opacity-50">
          Go to Dashboard
        </button>
      </div>
    </div>
  </div>
</template>
