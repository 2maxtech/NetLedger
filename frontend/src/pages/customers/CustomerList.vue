<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCustomers, createCustomer, deleteCustomer, type Customer } from '../../api/customers'
import { getPlans, type Plan } from '../../api/plans'
import { getRouters, getAreas, importFromRouter, type RouterType, type AreaType } from '../../api/routers'
import DataTable from '../../components/common/DataTable.vue'
import StatusBadge from '../../components/common/StatusBadge.vue'
import Pagination from '../../components/common/Pagination.vue'
import Modal from '../../components/common/Modal.vue'
import ConfirmDialog from '../../components/common/ConfirmDialog.vue'

const router = useRouter()

// List state
const customers = ref<Customer[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const search = ref('')
const statusFilter = ref('')

// Dropdown data
const plans = ref<Plan[]>([])
const routers = ref<RouterType[]>([])
const areas = ref<AreaType[]>([])

// Add customer modal
const showAddModal = ref(false)
const addLoading = ref(false)
const addForm = ref({
  full_name: '',
  email: '',
  phone: '',
  address: '',
  pppoe_username: '',
  pppoe_password: '',
  plan_id: '',
  billing_due_day: '15',
  router_id: '',
  area_id: '',
  mac_address: '',
})
const addError = ref('')

// Edit modal
const showEditModal = ref(false)
const editLoading = ref(false)
const editForm = ref({ ...addForm.value })
const editCustomerId = ref('')
const editError = ref('')

// Delete confirm
const showDeleteConfirm = ref(false)
const deleteLoading = ref(false)
const deleteTarget = ref<Customer | null>(null)
const deletePassword = ref('')
const deleteError = ref('')

// Import from MikroTik
const showImportModal = ref(false)
const importRouterId = ref('')
const importLoading = ref(false)
const importResult = ref<{ plans_created?: number; customers_created?: number; customers_skipped?: number; error?: string } | null>(null)

async function handleImport() {
  if (!importRouterId.value) return
  importLoading.value = true
  importResult.value = null
  try {
    const { data } = await importFromRouter(importRouterId.value)
    importResult.value = data
    fetchCustomers()
  } catch (e: any) {
    importResult.value = { error: e.response?.data?.detail || 'Import failed' }
  } finally {
    importLoading.value = false
  }
}

const columns = [
  { key: 'full_name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'pppoe_username', label: 'PPPoE Username' },
  { key: 'plan_name', label: 'Plan' },
  { key: 'status', label: 'Status' },
  { key: 'created_at', label: 'Created', width: '140px' },
  { key: 'actions', label: 'Actions', width: '160px', align: 'right' as const },
]

async function fetchCustomers() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (search.value) params.search = search.value
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await getCustomers(params)
    customers.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Failed to fetch customers', e)
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

function generatePassword() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
  let result = ''
  for (let i = 0; i < 8; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

function autoGeneratePassword() {
  addForm.value.pppoe_password = generatePassword()
}

function autoGenerateEditPassword() {
  editForm.value.pppoe_password = generatePassword()
}

function resetAddForm() {
  addForm.value = {
    full_name: '',
    email: '',
    phone: '',
    address: '',
    pppoe_username: '',
    pppoe_password: '',
    plan_id: '',
    billing_due_day: '15',
    router_id: '',
    area_id: '',
    mac_address: '',
  }
  addError.value = ''
}

function openAddModal() {
  resetAddForm()
  showAddModal.value = true
}

async function handleAdd() {
  addError.value = ''
  if (!addForm.value.full_name || !addForm.value.pppoe_username) {
    addError.value = 'Full name and PPPoE username are required.'
    return
  }
  if (!addForm.value.plan_id) {
    addError.value = 'Please select a plan.'
    return
  }
  addLoading.value = true
  try {
    const payload: Record<string, any> = { ...addForm.value }
    payload.billing_due_day = parseInt(payload.billing_due_day) || 15
    if (!payload.router_id) delete payload.router_id
    if (!payload.area_id) delete payload.area_id
    if (!payload.mac_address) delete payload.mac_address
    await createCustomer(payload)
    showAddModal.value = false
    await fetchCustomers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    addError.value = typeof detail === 'string' ? detail : 'Failed to create customer.'
  } finally {
    addLoading.value = false
  }
}

function openEditModal(customer: Customer) {
  editCustomerId.value = customer.id
  editForm.value = {
    full_name: customer.full_name,
    email: customer.email || '',
    phone: customer.phone || '',
    address: customer.address || '',
    pppoe_username: customer.pppoe_username,
    pppoe_password: '',
    plan_id: customer.plan_id || '',
    billing_due_day: String((customer as any).billing_due_day || 15),
    router_id: customer.router_id || '',
    area_id: customer.area_id || '',
    mac_address: customer.mac_address || '',
  }
  editError.value = ''
  showEditModal.value = true
}

async function handleEdit() {
  editError.value = ''
  if (!editForm.value.full_name || !editForm.value.pppoe_username) {
    editError.value = 'Full name and PPPoE username are required.'
    return
  }
  editLoading.value = true
  try {
    const { updateCustomer } = await import('../../api/customers')
    const payload: Record<string, any> = { ...editForm.value }
    payload.billing_due_day = parseInt(payload.billing_due_day) || 15
    if (!payload.pppoe_password) delete payload.pppoe_password
    if (!payload.plan_id) payload.plan_id = null
    if (!payload.router_id) payload.router_id = null
    if (!payload.area_id) payload.area_id = null
    if (!payload.mac_address) payload.mac_address = null
    await updateCustomer(editCustomerId.value, payload)
    showEditModal.value = false
    await fetchCustomers()
  } catch (e: any) {
    const detail = e.response?.data?.detail
    editError.value = typeof detail === 'string' ? detail : 'Failed to update customer.'
  } finally {
    editLoading.value = false
  }
}

function confirmDelete(customer: Customer) {
  deleteTarget.value = customer
  deletePassword.value = ''
  deleteError.value = ''
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTarget.value) return
  if (!deletePassword.value) {
    deleteError.value = 'Please enter your password to confirm.'
    return
  }
  deleteError.value = ''
  deleteLoading.value = true
  try {
    await deleteCustomer(deleteTarget.value.id, deletePassword.value)
    showDeleteConfirm.value = false
    deleteTarget.value = null
    await fetchCustomers()
  } catch (e: any) {
    deleteError.value = e.response?.data?.detail || 'Failed to delete customer'
  } finally {
    deleteLoading.value = false
  }
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

// Debounced search
let searchTimer: ReturnType<typeof setTimeout>
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchCustomers()
  }, 350)
})

watch(statusFilter, () => {
  page.value = 1
  fetchCustomers()
})

watch(page, () => {
  fetchCustomers()
})

onMounted(() => {
  fetchCustomers()
  loadDropdowns()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Customers</h1>
        <p class="text-sm text-gray-500 mt-1">Manage your subscriber accounts</p>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="showImportModal = true; importResult = null; importRouterId = ''"
          class="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 transition-colors"
        >
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm.75-11.25a.75.75 0 00-1.5 0v4.59L7.3 9.24a.75.75 0 00-1.1 1.02l3.25 3.5a.75.75 0 001.1 0l3.25-3.5a.75.75 0 10-1.1-1.02l-1.95 2.1V6.75z" clip-rule="evenodd"/></svg>
          Import from MikroTik
        </button>
        <button
          @click="openAddModal"
          class="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors"
        >
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          Add Customer
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3">
      <div class="relative flex-1 max-w-md">
        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg class="w-4 h-4 text-gray-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" />
          </svg>
        </div>
        <input
          v-model="search"
          type="text"
          placeholder="Search by name, email, or PPPoE username..."
          class="w-full pl-9 pr-4 py-2 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
        />
      </div>
      <select
        v-model="statusFilter"
        class="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
      >
        <option value="">All Statuses</option>
        <option value="active">Active</option>
        <option value="suspended">Suspended</option>
        <option value="disconnected">Disconnected</option>
        <option value="terminated">Terminated</option>
      </select>
    </div>

    <!-- Table -->
    <DataTable :columns="columns" :data="customers" :loading="loading" empty-text="No customers found">
      <template #full_name="{ row }">
        <span class="font-medium text-gray-900">{{ row.full_name }}</span>
      </template>
      <template #email="{ row }">
        <span class="text-gray-600">{{ row.email || '-' }}</span>
      </template>
      <template #pppoe_username="{ row }">
        <code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-700">{{ row.pppoe_username }}</code>
      </template>
      <template #plan_name="{ row }">
        <span class="text-gray-700">{{ row.plan?.name || '-' }}</span>
      </template>
      <template #status="{ row }">
        <StatusBadge :status="row.status" />
      </template>
      <template #created_at="{ row }">
        <span class="text-gray-500 text-xs">{{ formatDate(row.created_at) }}</span>
      </template>
      <template #actions="{ row }">
        <div class="flex items-center justify-end gap-1">
          <router-link
            :to="`/customers/${row.id}`"
            class="p-1.5 rounded-lg text-gray-400 hover:text-primary hover:bg-primary-light transition-colors"
            title="View"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z" />
              <path fill-rule="evenodd" d="M.664 10.59a1.651 1.651 0 010-1.186A10.004 10.004 0 0110 3c4.257 0 7.893 2.66 9.336 6.41.147.381.146.804 0 1.186A10.004 10.004 0 0110 17c-4.257 0-7.893-2.66-9.336-6.41zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" />
            </svg>
          </router-link>
          <button
            @click.stop="openEditModal(row)"
            class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
            title="Edit"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M2.695 14.763l-1.262 3.154a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.343z" />
            </svg>
          </button>
          <button
            @click.stop="confirmDelete(row)"
            class="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            title="Delete"
          >
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022 1.005 11.36A2.75 2.75 0 007.77 20h4.46a2.75 2.75 0 002.751-2.69l1.005-11.36.149.022a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 01.78.72l.5 6a.75.75 0 01-1.5.12l-.5-6a.75.75 0 01.72-.78zm3.62.72a.75.75 0 00-1.5-.12l-.5 6a.75.75 0 101.5.12l.5-6z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Pagination -->
    <Pagination
      v-if="total > pageSize"
      :page="page"
      :page-size="pageSize"
      :total="total"
      @update:page="page = $event"
    />

    <!-- Add Customer Modal -->
    <Modal :open="showAddModal" title="Add Customer" size="lg" @close="showAddModal = false">
      <div v-if="addError" class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {{ addError }}
      </div>
      <form @submit.prevent="handleAdd" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
            <input
              v-model="addForm.full_name"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              placeholder="Juan Dela Cruz"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              v-model="addForm.email"
              type="email"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              placeholder="juan@example.com"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              v-model="addForm.phone"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              placeholder="09171234567"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Address</label>
            <input
              v-model="addForm.address"
              type="text"
              class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              placeholder="123 Main St, Brgy. Example"
            />
          </div>
        </div>

        <div class="border-t border-gray-100 pt-4">
          <h4 class="text-sm font-medium text-gray-800 mb-3">PPPoE Credentials</h4>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">PPPoE Username *</label>
              <input
                v-model="addForm.pppoe_username"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                placeholder="juan.delacruz"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">PPPoE Password</label>
              <div class="flex gap-2">
                <input
                  v-model="addForm.pppoe_password"
                  type="text"
                  class="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                  placeholder="Password"
                />
                <button
                  type="button"
                  @click="autoGeneratePassword"
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
                v-model="addForm.plan_id"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option value="">Select a plan</option>
                <option v-for="plan in plans" :key="plan.id" :value="plan.id">
                  {{ plan.name }} - &#8369;{{ Number(plan.monthly_price).toLocaleString() }}/mo
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Billing Due Day</label>
              <select
                v-model="addForm.billing_due_day"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option v-for="d in 28" :key="d" :value="String(d)">{{ d }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">MAC Address</label>
              <input
                v-model="addForm.mac_address"
                type="text"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                placeholder="AA:BB:CC:DD:EE:FF"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Router</label>
              <select
                v-model="addForm.router_id"
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
                v-model="addForm.area_id"
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
          @click="showAddModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleAdd"
          :disabled="addLoading"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ addLoading ? 'Creating...' : 'Create Customer' }}
        </button>
      </template>
    </Modal>

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
              <label class="block text-sm font-medium text-gray-700 mb-1">Billing Due Day</label>
              <select
                v-model="editForm.billing_due_day"
                class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option v-for="d in 28" :key="d" :value="String(d)">{{ d }}</option>
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

    <!-- Delete Confirm -->
    <Modal :open="showDeleteConfirm" title="Delete Customer" @close="showDeleteConfirm = false">
      <div class="space-y-4">
        <div class="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
          <p class="text-sm text-red-700">
            This will <strong>permanently delete {{ deleteTarget?.full_name }}</strong> and remove the PPPoE secret from MikroTik. All invoices, payments, and records will be lost. This cannot be undone.
          </p>
        </div>
        <div v-if="deleteError" class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {{ deleteError }}
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Enter your password to confirm</label>
          <input
            v-model="deletePassword"
            type="password"
            placeholder="Your admin password"
            class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-red-300 focus:border-red-400 transition-colors"
            @keyup.enter="handleDelete"
          />
        </div>
        <div class="flex justify-end gap-3 pt-2">
          <button
            @click="showDeleteConfirm = false"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            @click="handleDelete"
            :disabled="deleteLoading || !deletePassword"
            class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ deleteLoading ? 'Deleting...' : 'Delete Customer' }}
          </button>
        </div>
      </div>
    </Modal>

    <!-- Import from MikroTik Modal -->
    <Modal :open="showImportModal" title="Import from MikroTik" size="md" @close="showImportModal = false">
      <div class="space-y-4">
        <p class="text-sm text-gray-600">
          Import existing PPPoE secrets and profiles from your MikroTik router. This will create customers and plans in NetLedger from your existing MikroTik configuration.
        </p>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Select Router</label>
          <select
            v-model="importRouterId"
            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          >
            <option value="">Choose a router...</option>
            <option v-for="r in routers" :key="r.id" :value="r.id">{{ r.name }} ({{ r.url }})</option>
          </select>
        </div>
        <div v-if="!routers.length" class="rounded-lg bg-amber-50 border border-amber-200 p-3">
          <p class="text-sm text-amber-700">No routers added yet. Go to <strong>Routers</strong> page to add your MikroTik first.</p>
        </div>
        <div v-if="importResult && !importResult.error" class="rounded-lg bg-green-50 border border-green-200 p-4">
          <p class="text-sm font-medium text-green-800">Import Complete</p>
          <ul class="mt-2 text-sm text-green-700 space-y-1">
            <li>Plans created: <strong>{{ importResult.plans_created }}</strong></li>
            <li>Customers imported: <strong>{{ importResult.customers_created }}</strong></li>
            <li>Skipped (already exist): <strong>{{ importResult.customers_skipped }}</strong></li>
          </ul>
        </div>
        <div v-if="importResult?.error" class="rounded-lg bg-red-50 border border-red-200 p-3">
          <p class="text-sm text-red-700">{{ importResult.error }}</p>
        </div>
      </div>
      <template #footer>
        <button @click="showImportModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
          Close
        </button>
        <button
          @click="handleImport"
          :disabled="importLoading || !importRouterId"
          class="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-hover rounded-lg disabled:opacity-50"
        >
          {{ importLoading ? 'Importing...' : 'Import Subscribers' }}
        </button>
      </template>
    </Modal>
  </div>
</template>
