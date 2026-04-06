<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getCustomer,
  updateCustomer,
  deleteCustomer,
  disconnectCustomer,
  reconnectCustomer,
  throttleCustomer,
  changePlan,
  getCustomerHistory,
  type Customer,
  type HistoryEvent,
} from '../../api/customers'
import { getPlans, type Plan } from '../../api/plans'
import { getRouters, getAreas, type RouterType, type AreaType } from '../../api/routers'
import { getInvoices, downloadInvoicePdf, type Invoice } from '../../api/billing'
import StatusBadge from '../../components/common/StatusBadge.vue'
import Modal from '../../components/common/Modal.vue'
import ConfirmDialog from '../../components/common/ConfirmDialog.vue'
import Pagination from '../../components/common/Pagination.vue'

const route = useRoute()
const router = useRouter()
const customerId = route.params.id as string

// Data
const customer = ref<Customer | null>(null)
const loading = ref(true)
const activeTab = ref<'overview' | 'billing' | 'history'>('overview')

// Dropdown data
const plans = ref<Plan[]>([])
const routers = ref<RouterType[]>([])
const areas = ref<AreaType[]>([])

// Billing tab
const invoices = ref<Invoice[]>([])
const invoicesTotal = ref(0)
const invoicesPage = ref(1)
const invoicesPageSize = 10
const invoicesLoading = ref(false)

// History tab
const historyEvents = ref<HistoryEvent[]>([])
const historyLoading = ref(false)

// Edit modal
const showEditModal = ref(false)
const editLoading = ref(false)
const editError = ref('')
const editForm = ref({
  full_name: '',
  email: '',
  phone: '',
  address: '',
  pppoe_username: '',
  pppoe_password: '',
  plan_id: '',
  router_id: '',
  area_id: '',
  mac_address: '',
})

// Change plan modal
const showChangePlanModal = ref(false)
const changePlanLoading = ref(false)
const selectedPlanId = ref('')

// Delete confirm
const showDeleteConfirm = ref(false)
const deleteLoading = ref(false)

// Action loading states
const actionLoading = ref(false)

// Computed
const canDisconnect = computed(() => customer.value?.status === 'active')
const canReconnect = computed(() => ['suspended', 'disconnected'].includes(customer.value?.status || ''))

const routerName = computed(() => {
  if (!customer.value?.router_id) return '-'
  const r = routers.value.find(r => r.id === customer.value!.router_id)
  return r?.name || '-'
})

const areaName = computed(() => {
  if (!customer.value?.area_id) return '-'
  const a = areas.value.find(a => a.id === customer.value!.area_id)
  return a?.name || '-'
})

async function fetchCustomer() {
  loading.value = true
  try {
    const { data } = await getCustomer(customerId)
    customer.value = data
  } catch (e) {
    console.error('Failed to fetch customer', e)
  } finally {
    loading.value = false
  }
}

async function loadDropdowns() {
  try {
    const [plansRes, routersRes, areasRes] = await Promise.all([
      getPlans({ active_only: true }),
      getRouters(),
      getAreas(),
    ])
    plans.value = plansRes.data
    routers.value = routersRes.data
    areas.value = areasRes.data
  } catch (e) {
    console.error('Failed to load dropdown data', e)
  }
}

async function fetchInvoices() {
  invoicesLoading.value = true
  try {
    const { data } = await getInvoices({
      customer_id: customerId,
      page: invoicesPage.value,
      size: invoicesPageSize,
    })
    invoices.value = data.items
    invoicesTotal.value = data.total
  } catch (e) {
    console.error('Failed to fetch invoices', e)
  } finally {
    invoicesLoading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    const { data } = await getCustomerHistory(customerId)
    historyEvents.value = data.events
  } catch (e) {
    console.error('Failed to fetch history', e)
  } finally {
    historyLoading.value = false
  }
}

// Actions
async function handleDisconnect() {
  actionLoading.value = true
  try {
    await disconnectCustomer(customerId)
    await fetchCustomer()
  } catch (e) {
    console.error('Failed to disconnect customer', e)
  } finally {
    actionLoading.value = false
  }
}

async function handleReconnect() {
  actionLoading.value = true
  try {
    await reconnectCustomer(customerId)
    await fetchCustomer()
  } catch (e) {
    console.error('Failed to reconnect customer', e)
  } finally {
    actionLoading.value = false
  }
}

async function handleThrottle() {
  actionLoading.value = true
  try {
    await throttleCustomer(customerId)
    await fetchCustomer()
  } catch (e) {
    console.error('Failed to throttle customer', e)
  } finally {
    actionLoading.value = false
  }
}

// Edit
function openEditModal() {
  if (!customer.value) return
  editForm.value = {
    full_name: customer.value.full_name,
    email: customer.value.email || '',
    phone: customer.value.phone || '',
    address: customer.value.address || '',
    pppoe_username: customer.value.pppoe_username,
    pppoe_password: '',
    plan_id: customer.value.plan_id || '',
    router_id: customer.value.router_id || '',
    area_id: customer.value.area_id || '',
    mac_address: customer.value.mac_address || '',
  }
  editError.value = ''
  showEditModal.value = true
}

function generatePassword() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
  let result = ''
  for (let i = 0; i < 8; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

function autoGenerateEditPassword() {
  editForm.value.pppoe_password = generatePassword()
}

async function handleEdit() {
  editError.value = ''
  if (!editForm.value.full_name || !editForm.value.pppoe_username) {
    editError.value = 'Full name and PPPoE username are required.'
    return
  }
  editLoading.value = true
  try {
    const payload: Record<string, any> = { ...editForm.value }
    if (!payload.pppoe_password) delete payload.pppoe_password
    if (!payload.plan_id) payload.plan_id = null
    if (!payload.router_id) payload.router_id = null
    if (!payload.area_id) payload.area_id = null
    if (!payload.mac_address) payload.mac_address = null
    await updateCustomer(customerId, payload)
    showEditModal.value = false
    await fetchCustomer()
  } catch (e: any) {
    editError.value = e.response?.data?.detail || 'Failed to update customer.'
  } finally {
    editLoading.value = false
  }
}

// Change Plan
function openChangePlanModal() {
  selectedPlanId.value = customer.value?.plan_id || ''
  showChangePlanModal.value = true
}

async function handleChangePlan() {
  if (!selectedPlanId.value) return
  changePlanLoading.value = true
  try {
    await changePlan(customerId, selectedPlanId.value)
    showChangePlanModal.value = false
    await fetchCustomer()
  } catch (e: any) {
    console.error('Failed to change plan', e)
  } finally {
    changePlanLoading.value = false
  }
}

// Delete
async function handleDelete() {
  deleteLoading.value = true
  try {
    await deleteCustomer(customerId)
    router.push('/customers')
  } catch (e: any) {
    console.error('Failed to delete customer', e)
  } finally {
    deleteLoading.value = false
  }
}

// Invoice PDF download
async function downloadPdf(invoice: Invoice) {
  try {
    const { data } = await downloadInvoicePdf(invoice.id)
    const url = window.URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `invoice-${invoice.id}.pdf`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Failed to download PDF', e)
  }
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

function formatCurrency(amount: number | string) {
  return '₱' + Number(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(async () => {
  await Promise.all([fetchCustomer(), loadDropdowns(), fetchInvoices()])
})
</script>

<template>
  <div class="space-y-6">
    <!-- Back link -->
    <router-link
      to="/customers"
      class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
    >
      <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clip-rule="evenodd" />
      </svg>
      Back to Customers
    </router-link>

    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <div class="animate-pulse space-y-4">
          <div class="h-8 bg-gray-100 rounded w-1/3" />
          <div class="h-4 bg-gray-100 rounded w-1/4" />
          <div class="flex gap-3 mt-4">
            <div class="h-9 bg-gray-100 rounded w-20" />
            <div class="h-9 bg-gray-100 rounded w-28" />
            <div class="h-9 bg-gray-100 rounded w-24" />
          </div>
        </div>
      </div>
    </template>

    <template v-else-if="customer">
      <!-- Header Card -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-4">
            <div class="w-14 h-14 rounded-full bg-primary-light flex items-center justify-center">
              <span class="text-xl font-bold text-primary">
                {{ customer.full_name.charAt(0).toUpperCase() }}
              </span>
            </div>
            <div>
              <div class="flex items-center gap-3">
                <h1 class="text-2xl font-bold text-gray-900">{{ customer.full_name }}</h1>
                <StatusBadge :status="customer.status" />
              </div>
              <p class="text-sm text-gray-500 mt-0.5">
                PPPoE: <code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{{ customer.pppoe_username }}</code>
              </p>
            </div>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="flex items-center gap-2 mt-5 pt-5 border-t border-gray-100">
          <button
            @click="openEditModal"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M2.695 14.763l-1.262 3.154a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.343z" />
            </svg>
            Edit
          </button>

          <button
            v-if="canDisconnect"
            @click="handleDisconnect"
            :disabled="actionLoading"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-amber-300 text-sm font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 transition-colors disabled:opacity-50"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M5.127 3.502L5.25 3.5h9.5c.041 0 .082 0 .123.002A2.251 2.251 0 0012.75 2h-5.5a2.25 2.25 0 00-2.123 1.502zM1 10.25A2.25 2.25 0 013.25 8h13.5A2.25 2.25 0 0119 10.25v5.5A2.25 2.25 0 0116.75 18H3.25A2.25 2.25 0 011 15.75v-5.5zM3.25 6.5c-.04 0-.082 0-.123.002A2.25 2.25 0 015.25 5h9.5c.98 0 1.814.627 2.123 1.502a3.819 3.819 0 00-.123-.002H3.25z" />
            </svg>
            Disconnect
          </button>

          <button
            v-if="canReconnect"
            @click="handleReconnect"
            :disabled="actionLoading"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-green-300 text-sm font-medium text-green-700 bg-green-50 hover:bg-green-100 transition-colors disabled:opacity-50"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.28a.75.75 0 00-.75.75v3.955a.75.75 0 001.5 0v-2.134l.228.228a7 7 0 0011.709-3.14.75.75 0 00-1.455-.364zM4.688 8.576a5.5 5.5 0 019.201-2.466l.312.311H11.77a.75.75 0 000 1.5h3.951a.75.75 0 00.75-.75V3.216a.75.75 0 00-1.5 0v2.134l-.228-.228A7 7 0 003.034 8.21a.75.75 0 001.455.364z" clip-rule="evenodd" />
            </svg>
            Reconnect
          </button>

          <button
            @click="handleThrottle"
            :disabled="actionLoading || customer.status !== 'active'"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 3.75a2 2 0 10-4 0 2 2 0 004 0zM17.25 4.5a.75.75 0 000-1.5h-5.5a.75.75 0 000 1.5h5.5zM5 3.75a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5a.75.75 0 01.75.75zM4.25 17a.75.75 0 000-1.5h-1.5a.75.75 0 000 1.5h1.5zM17.25 17a.75.75 0 000-1.5h-5.5a.75.75 0 000 1.5h5.5zM9 10a.75.75 0 01-.75.75h-5.5a.75.75 0 010-1.5h5.5A.75.75 0 019 10zM17.25 10.75a.75.75 0 000-1.5h-1.5a.75.75 0 000 1.5h1.5zM14 10a2 2 0 10-4 0 2 2 0 004 0zM10 16.25a2 2 0 10-4 0 2 2 0 004 0z" />
            </svg>
            Throttle
          </button>

          <button
            @click="openChangePlanModal"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M13.2 2.24a.75.75 0 00.04 1.06l2.1 1.95H6.75a.75.75 0 000 1.5h8.59l-2.1 1.95a.75.75 0 101.02 1.1l3.5-3.25a.75.75 0 000-1.1l-3.5-3.25a.75.75 0 00-1.06.04zm-6.4 8a.75.75 0 00-1.06-.04l-3.5 3.25a.75.75 0 000 1.1l3.5 3.25a.75.75 0 101.02-1.1l-2.1-1.95h8.59a.75.75 0 000-1.5H4.66l2.1-1.95a.75.75 0 00.04-1.06z" clip-rule="evenodd" />
            </svg>
            Change Plan
          </button>

          <div class="flex-1" />

          <button
            @click="showDeleteConfirm = true"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022 1.005 11.36A2.75 2.75 0 007.77 20h4.46a2.75 2.75 0 002.751-2.69l1.005-11.36.149.022a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 01.78.72l.5 6a.75.75 0 01-1.5.12l-.5-6a.75.75 0 01.72-.78zm3.62.72a.75.75 0 00-1.5-.12l-.5 6a.75.75 0 101.5.12l.5-6z" clip-rule="evenodd" />
            </svg>
            Delete
          </button>
        </div>
      </div>

      <!-- Tabs -->
      <div class="border-b border-gray-200">
        <nav class="flex gap-6">
          <button
            @click="activeTab = 'overview'"
            :class="[
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'overview'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            ]"
          >
            Overview
          </button>
          <button
            @click="activeTab = 'billing'; fetchInvoices()"
            :class="[
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'billing'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            ]"
          >
            Billing
          </button>
          <button
            @click="activeTab = 'history'; fetchHistory()"
            :class="[
              'pb-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === 'history'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            ]"
          >
            History
          </button>
        </nav>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Personal Information -->
        <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
          <h3 class="text-sm font-semibold text-gray-800 uppercase tracking-wider mb-4">Personal Information</h3>
          <dl class="space-y-4">
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Full Name</dt>
              <dd class="text-sm font-medium text-gray-900">{{ customer.full_name }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Email</dt>
              <dd class="text-sm text-gray-900">{{ customer.email || '-' }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Phone</dt>
              <dd class="text-sm text-gray-900">{{ customer.phone || '-' }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Address</dt>
              <dd class="text-sm text-gray-900 text-right max-w-[60%]">{{ customer.address || '-' }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Created</dt>
              <dd class="text-sm text-gray-900">{{ formatDate(customer.created_at) }}</dd>
            </div>
          </dl>
        </div>

        <!-- Service Details -->
        <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
          <h3 class="text-sm font-semibold text-gray-800 uppercase tracking-wider mb-4">Service Details</h3>
          <dl class="space-y-4">
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">PPPoE Username</dt>
              <dd class="text-sm text-gray-900">
                <code class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{{ customer.pppoe_username }}</code>
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Plan</dt>
              <dd class="text-sm font-medium text-gray-900">{{ customer.plan?.name || '-' }}</dd>
            </div>
            <div v-if="customer.plan" class="flex justify-between">
              <dt class="text-sm text-gray-500">Monthly Price</dt>
              <dd class="text-sm text-gray-900">{{ formatCurrency(customer.plan.monthly_price) }}</dd>
            </div>
            <div v-if="customer.plan" class="flex justify-between">
              <dt class="text-sm text-gray-500">Speed</dt>
              <dd class="text-sm text-gray-900">
                {{ customer.plan.download_mbps }} / {{ customer.plan.upload_mbps }} Mbps
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Router</dt>
              <dd class="text-sm text-gray-900">{{ routerName }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">Area</dt>
              <dd class="text-sm text-gray-900">{{ areaName }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-sm text-gray-500">MAC Address</dt>
              <dd class="text-sm text-gray-900">
                <code v-if="customer.mac_address" class="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{{ customer.mac_address }}</code>
                <span v-else>-</span>
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <!-- Billing Tab -->
      <div v-if="activeTab === 'billing'" class="space-y-4">
        <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="bg-gray-50 border-b border-gray-100">
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Invoice</th>
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Amount</th>
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Due Date</th>
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Status</th>
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Issued</th>
                  <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <template v-if="invoicesLoading">
                  <tr v-for="i in 5" :key="i">
                    <td v-for="j in 6" :key="j" class="px-4 py-3">
                      <div class="h-4 bg-gray-100 rounded animate-pulse" />
                    </td>
                  </tr>
                </template>
                <tr v-else-if="!invoices.length">
                  <td colspan="6" class="px-4 py-12 text-center text-gray-400">
                    No invoices found for this customer
                  </td>
                </tr>
                <tr v-else v-for="inv in invoices" :key="inv.id" class="hover:bg-gray-50/50 transition-colors">
                  <td class="px-4 py-3 text-sm">
                    <code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-600">{{ inv.id.substring(0, 8) }}</code>
                  </td>
                  <td class="px-4 py-3 text-sm text-right font-medium text-gray-900 tabular-nums">
                    {{ formatCurrency(inv.amount) }}
                  </td>
                  <td class="px-4 py-3 text-sm text-gray-700">{{ formatDate(inv.due_date) }}</td>
                  <td class="px-4 py-3"><StatusBadge :status="inv.status" /></td>
                  <td class="px-4 py-3 text-sm text-gray-500">{{ formatDate(inv.issued_at) }}</td>
                  <td class="px-4 py-3 text-right">
                    <button
                      @click="downloadPdf(inv)"
                      class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                      title="Download PDF"
                    >
                      <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                        <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                      </svg>
                      PDF
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <Pagination
          v-if="invoicesTotal > invoicesPageSize"
          :page="invoicesPage"
          :page-size="invoicesPageSize"
          :total="invoicesTotal"
          @update:page="invoicesPage = $event; fetchInvoices()"
        />
      </div>

      <!-- History Tab -->
      <div v-if="activeTab === 'history'" class="space-y-4">
        <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
          <!-- Loading -->
          <div v-if="historyLoading" class="space-y-4">
            <div v-for="i in 5" :key="i" class="flex gap-4">
              <div class="w-2 h-2 mt-2 rounded-full bg-gray-200 animate-pulse shrink-0" />
              <div class="flex-1 space-y-2">
                <div class="h-4 w-48 bg-gray-100 rounded animate-pulse" />
                <div class="h-3 w-32 bg-gray-50 rounded animate-pulse" />
              </div>
            </div>
          </div>

          <!-- Empty -->
          <div v-else-if="!historyEvents.length" class="text-center py-12">
            <svg class="w-10 h-10 text-gray-300 mx-auto mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-sm text-gray-400">No history yet</p>
          </div>

          <!-- Timeline -->
          <div v-else class="relative">
            <div class="absolute left-[5px] top-2 bottom-2 w-px bg-gray-200" />
            <div v-for="event in historyEvents" :key="event.ref_id + event.date" class="relative flex gap-4 pb-5 last:pb-0">
              <!-- Dot -->
              <div
                :class="[
                  'w-[11px] h-[11px] mt-1.5 rounded-full border-2 shrink-0 z-10',
                  event.type === 'payment' || event.type === 'invoice_paid'
                    ? 'bg-green-500 border-green-200'
                    : event.type === 'enforcement' && event.status === 'disconnected'
                    ? 'bg-red-500 border-red-200'
                    : event.type === 'enforcement' && event.status === 'suspended'
                    ? 'bg-amber-500 border-amber-200'
                    : event.type === 'enforcement' && event.status === 'active'
                    ? 'bg-green-500 border-green-200'
                    : event.type === 'invoice' && event.status === 'overdue'
                    ? 'bg-red-400 border-red-200'
                    : event.type === 'notification'
                    ? 'bg-blue-400 border-blue-200'
                    : 'bg-gray-400 border-gray-200'
                ]"
              />
              <!-- Content -->
              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-2">
                  <p class="text-sm font-medium text-gray-900">{{ event.title }}</p>
                  <StatusBadge v-if="event.type !== 'notification'" :status="event.status" />
                </div>
                <p v-if="event.detail" class="text-xs text-gray-500 mt-0.5">{{ event.detail }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ formatDate(event.date) }} {{ new Date(event.date).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Not found -->
    <div v-else-if="!loading" class="rounded-xl bg-white shadow-sm border border-gray-100 p-12 text-center">
      <svg class="w-12 h-12 text-gray-300 mx-auto mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15.182 16.318A4.486 4.486 0 0012.016 15a4.486 4.486 0 00-3.198 1.318M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
      </svg>
      <h3 class="text-lg font-medium text-gray-900 mb-1">Customer not found</h3>
      <p class="text-sm text-gray-500 mb-4">The customer you're looking for doesn't exist or has been removed.</p>
      <router-link to="/customers" class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors">
        Back to Customers
      </router-link>
    </div>

    <!-- Edit Customer Modal -->
    <Modal :open="showEditModal" title="Edit Customer" size="lg" @close="showEditModal = false">
      <div v-if="editError" class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {{ editError }}
      </div>
      <form @submit.prevent="handleEdit" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
            <input
              v-model="editForm.full_name"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              v-model="editForm.email"
              type="email"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              v-model="editForm.phone"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Address</label>
            <input
              v-model="editForm.address"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
        </div>

        <div class="border-t border-gray-100 pt-4">
          <h4 class="text-sm font-medium text-gray-800 mb-3">PPPoE Credentials</h4>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">PPPoE Username *</label>
              <input
                v-model="editForm.pppoe_username"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">PPPoE Password</label>
              <div class="flex gap-2">
                <input
                  v-model="editForm.pppoe_password"
                  type="text"
                  class="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                  placeholder="Leave blank to keep current"
                />
                <button
                  type="button"
                  @click="autoGenerateEditPassword"
                  class="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50 transition-colors whitespace-nowrap"
                  title="Auto-generate password"
                >
                  <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H4.28a.75.75 0 00-.75.75v3.955a.75.75 0 001.5 0v-2.134l.228.228a7 7 0 0011.709-3.14.75.75 0 00-1.455-.364zM4.688 8.576a5.5 5.5 0 019.201-2.466l.312.311H11.77a.75.75 0 000 1.5h3.951a.75.75 0 00.75-.75V3.216a.75.75 0 00-1.5 0v2.134l-.228-.228A7 7 0 003.034 8.21a.75.75 0 001.455.364z" clip-rule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="border-t border-gray-100 pt-4">
          <h4 class="text-sm font-medium text-gray-800 mb-3">Service Details</h4>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Plan</label>
              <select
                v-model="editForm.plan_id"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option value="">No plan</option>
                <option v-for="plan in plans" :key="plan.id" :value="plan.id">
                  {{ plan.name }} - &#8369;{{ Number(plan.monthly_price).toLocaleString() }}/mo
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">MAC Address</label>
              <input
                v-model="editForm.mac_address"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                placeholder="AA:BB:CC:DD:EE:FF"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Router</label>
              <select
                v-model="editForm.router_id"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option value="">No router assigned</option>
                <option v-for="r in routers" :key="r.id" :value="r.id">
                  {{ r.name }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Area</label>
              <select
                v-model="editForm.area_id"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option value="">No area assigned</option>
                <option v-for="a in areas" :key="a.id" :value="a.id">
                  {{ a.name }}
                </option>
              </select>
            </div>
          </div>
        </div>
      </form>
      <template #footer>
        <button
          @click="showEditModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleEdit"
          :disabled="editLoading"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ editLoading ? 'Saving...' : 'Save Changes' }}
        </button>
      </template>
    </Modal>

    <!-- Change Plan Modal -->
    <Modal :open="showChangePlanModal" title="Change Plan" size="sm" @close="showChangePlanModal = false">
      <div class="space-y-4">
        <p class="text-sm text-gray-600">Select a new plan for <strong>{{ customer?.full_name }}</strong>.</p>
        <div class="space-y-2">
          <label
            v-for="plan in plans"
            :key="plan.id"
            :class="[
              'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
              selectedPlanId === plan.id
                ? 'border-primary bg-primary-light'
                : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
            ]"
          >
            <input
              type="radio"
              v-model="selectedPlanId"
              :value="plan.id"
              class="text-primary focus:ring-primary"
            />
            <div class="flex-1">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-900">{{ plan.name }}</span>
                <span class="text-sm font-semibold text-gray-900 tabular-nums">{{ formatCurrency(plan.monthly_price) }}/mo</span>
              </div>
              <span class="text-xs text-gray-500">{{ plan.download_mbps }}/{{ plan.upload_mbps }} Mbps</span>
              <span
                v-if="customer?.plan_id === plan.id"
                class="ml-2 text-xs text-primary font-medium"
              >
                (current)
              </span>
            </div>
          </label>
        </div>
      </div>
      <template #footer>
        <button
          @click="showChangePlanModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleChangePlan"
          :disabled="changePlanLoading || selectedPlanId === customer?.plan_id"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ changePlanLoading ? 'Changing...' : 'Change Plan' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Customer"
      :message="`Are you sure you want to permanently delete ${customer?.full_name}? This action cannot be undone and will remove all associated PPPoE sessions, invoices, and billing records.`"
      confirm-text="Delete Customer"
      danger
      :loading="deleteLoading"
      @confirm="handleDelete"
      @cancel="showDeleteConfirm = false"
    />
  </div>
</template>
