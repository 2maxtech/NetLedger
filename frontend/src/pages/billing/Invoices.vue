<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getInvoices, generateInvoices, downloadInvoicePdf, deleteInvoice, type Invoice } from '../../api/billing'
import { getCustomers, type Customer } from '../../api/customers'
import { bulkMarkPaid, bulkSendNotification, bulkDeleteInvoices } from '../../api/bulk'
import { useAuth } from '../../composables/useAuth'
import StatusBadge from '../../components/common/StatusBadge.vue'
import Modal from '../../components/common/Modal.vue'
import ConfirmDialog from '../../components/common/ConfirmDialog.vue'
import Pagination from '../../components/common/Pagination.vue'
import SkeletonTable from '../../components/SkeletonTable.vue'
import EmptyState from '../../components/EmptyState.vue'

const { user } = useAuth()
const isDemo = computed(() => user.value?.is_demo === true)

const invoices = ref<Invoice[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// Filters
const filterStatus = ref('')
const filterFromDate = ref('')
const filterToDate = ref('')

// Generate All confirm
const showGenerateAllConfirm = ref(false)
const generateAllLoading = ref(false)

// Generate for Customer modal
const showGenerateModal = ref(false)
const generateCustomerLoading = ref(false)
const customerSearch = ref('')
const customerResults = ref<Customer[]>([])
const selectedCustomer = ref<Customer | null>(null)
const customerSearchLoading = ref(false)
const showCustomerDropdown = ref(false)

// Delete confirm
const showDeleteConfirm = ref(false)
const deleteTarget = ref<Invoice | null>(null)
const deleteLoading = ref(false)

// Bulk selection
const selectedIds = ref<Set<string>>(new Set())
const allSelected = computed(() => invoices.value.length > 0 && invoices.value.every(inv => selectedIds.value.has(inv.id)))
const someSelected = computed(() => invoices.value.some(inv => selectedIds.value.has(inv.id)) && !allSelected.value)
const bulkLoading = ref(false)
const bulkMessage = ref('')

function toggleSelectAll() {
  if (allSelected.value) {
    invoices.value.forEach(inv => selectedIds.value.delete(inv.id))
  } else {
    invoices.value.forEach(inv => selectedIds.value.add(inv.id))
  }
  selectedIds.value = new Set(selectedIds.value)
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function clearSelection() {
  selectedIds.value = new Set()
  bulkMessage.value = ''
}

async function handleBulkMarkPaid() {
  const ids = Array.from(selectedIds.value)
  if (!confirm(`Mark ${ids.length} invoice(s) as paid?`)) return
  bulkLoading.value = true
  bulkMessage.value = ''
  try {
    const { data } = await bulkMarkPaid(ids)
    bulkMessage.value = `Marked paid: ${data.success} success, ${data.failed} failed`
    clearSelection()
    fetchInvoices()
  } catch (e: any) {
    bulkMessage.value = e.response?.data?.detail || 'Bulk mark paid failed'
  } finally {
    bulkLoading.value = false
  }
}

async function handleBulkSendNotification() {
  const ids = Array.from(selectedIds.value)
  if (!confirm(`Send notification for ${ids.length} invoice(s)?`)) return
  bulkLoading.value = true
  bulkMessage.value = ''
  try {
    const { data } = await bulkSendNotification(ids)
    bulkMessage.value = `Notifications sent: ${data.success} success, ${data.failed} failed`
    clearSelection()
    fetchInvoices()
  } catch (e: any) {
    bulkMessage.value = e.response?.data?.detail || 'Bulk notification failed'
  } finally {
    bulkLoading.value = false
  }
}

// Bulk delete
const showDeletePasswordModal = ref(false)
const deletePassword = ref('')
const deleteError = ref('')

function handleBulkDelete() {
  deletePassword.value = ''
  deleteError.value = ''
  showDeletePasswordModal.value = true
}

async function confirmBulkDelete() {
  if (!deletePassword.value) { deleteError.value = 'Password is required'; return }
  const ids = Array.from(selectedIds.value)
  bulkLoading.value = true
  deleteError.value = ''
  try {
    const { data } = await bulkDeleteInvoices(ids, deletePassword.value)
    bulkMessage.value = `Deleted: ${data.success} success, ${data.failed} failed`
    if (data.failed > 0 && data.errors.length > 0) {
      bulkMessage.value += ` (${data.errors.map((e: any) => e.error).join(', ')})`
    }
    showDeletePasswordModal.value = false
    clearSelection()
    fetchInvoices()
  } catch (e: any) {
    deleteError.value = e.response?.data?.detail || 'Delete failed'
  } finally {
    bulkLoading.value = false
  }
}

async function fetchInvoices() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: pageSize }
    if (filterStatus.value) params.status = filterStatus.value
    if (filterFromDate.value) params.from_date = filterFromDate.value
    if (filterToDate.value) params.to_date = filterToDate.value
    const { data } = await getInvoices(params)
    invoices.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Failed to fetch invoices', e)
  } finally {
    loading.value = false
  }
}

watch(page, () => {
  clearSelection()
  fetchInvoices()
})

function applyFilters() {
  page.value = 1
  clearSelection()
  fetchInvoices()
}

// Customer search with debounce
let searchTimeout: ReturnType<typeof setTimeout> | null = null
function onCustomerSearch() {
  showCustomerDropdown.value = true
  selectedCustomer.value = null
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(async () => {
    if (!customerSearch.value.trim()) {
      customerResults.value = []
      return
    }
    customerSearchLoading.value = true
    try {
      const { data } = await getCustomers({ search: customerSearch.value, page_size: 10 })
      customerResults.value = data.items
    } catch (e) {
      console.error('Customer search failed', e)
    } finally {
      customerSearchLoading.value = false
    }
  }, 300)
}

function selectCustomer(c: Customer) {
  selectedCustomer.value = c
  customerSearch.value = c.full_name
  showCustomerDropdown.value = false
}

async function handleGenerateForCustomer() {
  if (!selectedCustomer.value) return
  generateCustomerLoading.value = true
  try {
    await generateInvoices(selectedCustomer.value.id)
    showGenerateModal.value = false
    customerSearch.value = ''
    selectedCustomer.value = null
    fetchInvoices()
  } catch (e) {
    console.error('Generate failed', e)
  } finally {
    generateCustomerLoading.value = false
  }
}

async function handleGenerateAll() {
  generateAllLoading.value = true
  try {
    await generateInvoices()
    showGenerateAllConfirm.value = false
    fetchInvoices()
  } catch (e) {
    console.error('Generate all failed', e)
  } finally {
    generateAllLoading.value = false
  }
}

async function handleDownloadPdf(inv: Invoice) {
  try {
    const { data } = await downloadInvoicePdf(inv.id)
    const url = window.URL.createObjectURL(new Blob([data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `invoice-${inv.id}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    console.error('PDF download failed', e)
  }
}

function handlePrint(inv: Invoice) {
  window.open(`/api/v1/billing/invoices/${inv.id}/pdf`, '_blank')
}

function openDeleteConfirm(inv: Invoice) {
  deleteTarget.value = inv
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  try {
    await deleteInvoice(deleteTarget.value.id)
    showDeleteConfirm.value = false
    deleteTarget.value = null
    fetchInvoices()
  } catch (e: any) {
    alert(e.response?.data?.detail || 'Delete failed')
  } finally {
    deleteLoading.value = false
  }
}

function formatCurrency(val: number | string) {
  return '₱' + Number(val).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function exportCsv() {
  const token = localStorage.getItem('token')
  const params = new URLSearchParams({ format: 'csv' })
  if (filterStatus.value) params.set('status', filterStatus.value)
  if (filterFromDate.value) params.set('from_date', filterFromDate.value)
  if (filterToDate.value) params.set('to_date', filterToDate.value)
  const response = await fetch(`/api/v1/billing/invoices/?${params}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'invoices.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(fetchInvoices)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <h1 class="text-2xl font-bold text-gray-900">Invoices</h1>
      <div class="flex items-center gap-3">
        <button
          @click="showGenerateModal = true"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
        >
          Generate for Customer
        </button>
        <button
          @click="showGenerateAllConfirm = true"
          class="px-4 py-2 text-sm font-medium text-primary bg-orange-50 border border-orange-200 rounded-lg hover:bg-orange-100 transition-colors"
        >
          Generate All
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
      <div class="flex flex-wrap items-end gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Status</label>
          <select
            v-model="filterStatus"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="">All</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="overdue">Overdue</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">From</label>
          <input
            v-model="filterFromDate"
            type="date"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">To</label>
          <input
            v-model="filterToDate"
            type="date"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <button
          @click="applyFilters"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
        >
          <svg class="w-4 h-4 inline-block mr-1 -mt-0.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" /></svg>
          Refresh
        </button>
        <button
          @click="exportCsv"
          class="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          Export CSV
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="px-3 py-3 w-10">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  :indeterminate="someSelected"
                  @change="toggleSelectAll"
                  class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary/30 cursor-pointer"
                />
              </th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Customer</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Amount</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Paid</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Due Date</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Status</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Issued</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <!-- Loading -->
            <template v-if="loading">
              <tr><td :colspan="8" class="p-0"><SkeletonTable :cols="8" :rows="5" /></td></tr>
            </template>
            <!-- Empty -->
            <tr v-else-if="!invoices.length">
              <td colspan="8">
                <EmptyState
                  icon="receipt"
                  title="No invoices yet"
                  description="Invoices are generated automatically based on your billing cycle, or you can generate them manually."
                  :actions="[{ label: 'Configure Billing', to: '/settings', primary: true }]"
                />
              </td>
            </tr>
            <!-- Rows -->
            <tr v-else v-for="inv in invoices" :key="inv.id" class="hover:bg-gray-50/50 transition-colors">
              <td class="px-3 py-3 w-10">
                <input
                  type="checkbox"
                  :checked="selectedIds.has(inv.id)"
                  @change="toggleSelect(inv.id)"
                  class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary/30 cursor-pointer"
                />
              </td>
              <td class="px-4 py-3 text-sm text-gray-700 font-medium">{{ inv.customer_name }}</td>
              <td class="px-4 py-3 text-sm text-gray-700 text-right">{{ formatCurrency(inv.amount) }}</td>
              <td class="px-4 py-3 text-sm text-gray-700 text-right">{{ formatCurrency(inv.total_paid) }}</td>
              <td class="px-4 py-3 text-sm text-gray-700">{{ dayjs(inv.due_date).format('MMM D, YYYY') }}</td>
              <td class="px-4 py-3"><StatusBadge :status="inv.status" /></td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ dayjs(inv.issued_at).format('MMM D, YYYY') }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    @click="handleDownloadPdf(inv)"
                    title="Download PDF"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-primary hover:bg-orange-50 transition-colors"
                  >
                    <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
                  </button>
                  <button
                    @click="handlePrint(inv)"
                    title="Print"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                  >
                    <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5 4v3H4a2 2 0 00-2 2v3a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2V9a2 2 0 00-2-2h-1V4a2 2 0 00-2-2H7a2 2 0 00-2 2zm8 0H7v3h6V4zm0 8H7v4h6v-4z" clip-rule="evenodd" /></svg>
                  </button>
                  <button
                    v-if="inv.status !== 'paid'"
                    @click="openDeleteConfirm(inv)"
                    title="Delete invoice"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Pagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @update:page="page = $event"
      />
    </div>

    <!-- Generate for Customer Modal -->
    <Modal :open="showGenerateModal" title="Generate Invoice for Customer" @close="showGenerateModal = false; customerSearch = ''; selectedCustomer = null">
      <div class="space-y-4">
        <div class="relative">
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Search Customer</label>
          <input
            v-model="customerSearch"
            @input="onCustomerSearch"
            @focus="showCustomerDropdown = true"
            type="text"
            placeholder="Type customer name..."
            class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
          <!-- Dropdown -->
          <div
            v-if="showCustomerDropdown && (customerResults.length || customerSearchLoading)"
            class="absolute z-10 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg max-h-48 overflow-y-auto"
          >
            <div v-if="customerSearchLoading" class="px-4 py-3 text-sm text-gray-400">Searching...</div>
            <button
              v-else
              v-for="c in customerResults"
              :key="c.id"
              @click="selectCustomer(c)"
              class="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors"
            >
              <span class="font-medium text-gray-800">{{ c.full_name }}</span>
              <span class="text-gray-400 ml-2">{{ c.pppoe_username }}</span>
            </button>
          </div>
        </div>
        <div v-if="selectedCustomer" class="rounded-lg bg-orange-50 border border-orange-100 px-4 py-3 text-sm text-gray-700">
          Selected: <strong>{{ selectedCustomer.full_name }}</strong>
          <span v-if="selectedCustomer.plan" class="text-gray-500 ml-1">({{ selectedCustomer.plan.name }})</span>
        </div>
      </div>
      <template #footer>
        <button
          @click="showGenerateModal = false; customerSearch = ''; selectedCustomer = null"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleGenerateForCustomer"
          :disabled="!selectedCustomer || generateCustomerLoading"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ generateCustomerLoading ? 'Generating...' : 'Generate' }}
        </button>
      </template>
    </Modal>

    <!-- Generate All Confirm -->
    <ConfirmDialog
      :open="showGenerateAllConfirm"
      title="Generate All Invoices"
      message="This will generate invoices for all eligible customers. Are you sure you want to proceed?"
      confirm-text="Generate All"
      :loading="generateAllLoading"
      @confirm="handleGenerateAll"
      @cancel="showGenerateAllConfirm = false"
    />

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete Invoice"
      :message="`Permanently delete invoice for ${deleteTarget?.customer_name} (${formatCurrency(deleteTarget?.amount || 0)})? This cannot be undone.`"
      confirm-text="Delete"
      :danger="true"
      :loading="deleteLoading"
      @confirm="handleDelete"
      @cancel="showDeleteConfirm = false; deleteTarget = null"
    />

    <!-- Bulk Action Floating Bar -->
    <Teleport to="body">
      <transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="translate-y-full opacity-0"
        enter-to-class="translate-y-0 opacity-100"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="translate-y-0 opacity-100"
        leave-to-class="translate-y-full opacity-0"
      >
        <div v-if="!isDemo && selectedIds.size > 0" class="fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 shadow-[0_-4px_12px_rgba(0,0,0,0.1)] px-6 py-3 flex items-center justify-between ml-0 lg:ml-64">
          <div class="flex items-center gap-3">
            <span class="text-sm font-semibold text-gray-800 dark:text-gray-200">{{ selectedIds.size }} selected</span>
            <button @click="clearSelection" class="text-xs text-gray-500 hover:text-gray-700 underline">Clear</button>
            <span v-if="bulkMessage" class="text-xs text-green-600 font-medium ml-2">{{ bulkMessage }}</span>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="handleBulkMarkPaid"
              :disabled="bulkLoading"
              class="px-3 py-1.5 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Mark as Paid
            </button>
            <button
              @click="handleBulkSendNotification"
              :disabled="bulkLoading"
              class="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Send Notification
            </button>
            <button
              @click="handleBulkDelete"
              :disabled="bulkLoading"
              class="px-3 py-1.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Bulk Delete Password Modal -->
    <Modal :show="showDeletePasswordModal" title="Confirm Delete" @close="showDeletePasswordModal = false">
      <p class="text-sm text-gray-600 mb-1">You are about to delete <strong>{{ selectedIds.size }} invoice(s)</strong>.</p>
      <p class="text-sm text-red-600 mb-4">Paid invoices will be skipped. This action cannot be undone.</p>
      <div v-if="deleteError" class="mb-3 rounded-lg px-3 py-2 text-sm bg-red-50 border border-red-200 text-red-700">{{ deleteError }}</div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1.5">Enter your password to confirm</label>
        <input v-model="deletePassword" type="password" placeholder="Your admin password" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-red-300 focus:border-red-400" @keyup.enter="confirmBulkDelete" />
      </div>
      <div class="flex justify-end gap-2 mt-4">
        <button @click="showDeletePasswordModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200">Cancel</button>
        <button @click="confirmBulkDelete" :disabled="bulkLoading || !deletePassword" class="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50">
          {{ bulkLoading ? 'Deleting...' : 'Delete Invoices' }}
        </button>
      </div>
    </Modal>
  </div>
</template>
