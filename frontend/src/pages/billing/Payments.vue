<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getPayments, recordPayment, getInvoices, type Payment, type Invoice } from '../../api/billing'
import Modal from '../../components/common/Modal.vue'
import Pagination from '../../components/common/Pagination.vue'

const payments = ref<Payment[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// Filters
const filterFromDate = ref('')
const filterToDate = ref('')

// Record Payment modal
const showRecordModal = ref(false)
const recordLoading = ref(false)
const unpaidInvoices = ref<Invoice[]>([])
const unpaidLoading = ref(false)

const form = ref({
  invoice_id: '',
  amount: '',
  method: 'cash',
  reference_number: '',
})

async function fetchPayments() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, size: pageSize }
    if (filterFromDate.value) params.from_date = filterFromDate.value
    if (filterToDate.value) params.to_date = filterToDate.value
    const { data } = await getPayments(params)
    payments.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Failed to fetch payments', e)
  } finally {
    loading.value = false
  }
}

watch(page, fetchPayments)

function applyFilters() {
  page.value = 1
  fetchPayments()
}

async function fetchUnpaidInvoices() {
  unpaidLoading.value = true
  try {
    const { data } = await getInvoices({ status: 'pending', size: 100 })
    const { data: overdueData } = await getInvoices({ status: 'overdue', size: 100 })
    unpaidInvoices.value = [...data.items, ...overdueData.items]
  } catch (e) {
    console.error('Failed to fetch unpaid invoices', e)
  } finally {
    unpaidLoading.value = false
  }
}

function openRecordModal() {
  form.value = { invoice_id: '', amount: '', method: 'cash', reference_number: '' }
  showRecordModal.value = true
  fetchUnpaidInvoices()
}

function onInvoiceSelect() {
  const inv = unpaidInvoices.value.find(i => i.id === form.value.invoice_id)
  if (inv) {
    const remaining = Number(inv.amount) - Number(inv.total_paid)
    form.value.amount = remaining > 0 ? remaining.toFixed(2) : Number(inv.amount).toFixed(2)
  }
}

async function handleRecordPayment() {
  if (!form.value.invoice_id || !form.value.amount) return
  recordLoading.value = true
  try {
    const payload: any = {
      invoice_id: form.value.invoice_id,
      amount: parseFloat(form.value.amount),
      method: form.value.method,
    }
    if (form.value.reference_number.trim()) {
      payload.reference_number = form.value.reference_number.trim()
    }
    await recordPayment(payload)
    showRecordModal.value = false
    fetchPayments()
  } catch (e) {
    console.error('Record payment failed', e)
  } finally {
    recordLoading.value = false
  }
}

function formatCurrency(val: number | string) {
  return '₱' + Number(val).toLocaleString('en-PH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(fetchPayments)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <h1 class="text-2xl font-bold text-gray-900">Payments</h1>
      <button
        @click="openRecordModal"
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
      >
        Record Payment
      </button>
    </div>

    <!-- Filters -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
      <div class="flex flex-wrap items-end gap-4">
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
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Customer</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Amount</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Method</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Reference</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Invoice Amt</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Received</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <!-- Loading -->
            <template v-if="loading">
              <tr v-for="i in 5" :key="i">
                <td v-for="j in 6" :key="j" class="px-4 py-3">
                  <div class="h-4 bg-gray-100 rounded animate-pulse" />
                </td>
              </tr>
            </template>
            <!-- Empty -->
            <tr v-else-if="!payments.length">
              <td colspan="6" class="px-4 py-12 text-center text-gray-400">No payments found</td>
            </tr>
            <!-- Rows -->
            <tr v-else v-for="pmt in payments" :key="pmt.id" class="hover:bg-gray-50/50 transition-colors">
              <td class="px-4 py-3 text-sm text-gray-700 font-medium">{{ pmt.customer_name }}</td>
              <td class="px-4 py-3 text-sm text-gray-700 text-right font-medium">{{ formatCurrency(pmt.amount) }}</td>
              <td class="px-4 py-3 text-sm text-gray-700">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md bg-gray-100 text-gray-600 text-xs font-medium capitalize">
                  {{ pmt.method.replace(/_/g, ' ') }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ pmt.reference_number || '---' }}</td>
              <td class="px-4 py-3 text-sm text-gray-500 text-right">{{ formatCurrency(pmt.invoice_amount) }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ dayjs(pmt.received_at).format('MMM D, YYYY h:mm A') }}</td>
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

    <!-- Record Payment Modal -->
    <Modal :open="showRecordModal" title="Record Payment" size="md" @close="showRecordModal = false">
      <div class="space-y-4">
        <!-- Invoice select -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Invoice</label>
          <select
            v-model="form.invoice_id"
            @change="onInvoiceSelect"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="" disabled>Select an unpaid invoice</option>
            <option v-if="unpaidLoading" value="" disabled>Loading invoices...</option>
            <option
              v-for="inv in unpaidInvoices"
              :key="inv.id"
              :value="inv.id"
            >
              {{ inv.customer_name }} - {{ formatCurrency(inv.amount) }} (due {{ dayjs(inv.due_date).format('MMM D') }})
            </option>
          </select>
        </div>

        <!-- Amount -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Amount (₱)</label>
          <input
            v-model="form.amount"
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>

        <!-- Method -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Payment Method</label>
          <select
            v-model="form.method"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank Transfer</option>
            <option value="gcash">GCash</option>
            <option value="maya">Maya</option>
            <option value="check">Check</option>
            <option value="other">Other</option>
          </select>
        </div>

        <!-- Reference Number -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Reference Number</label>
          <input
            v-model="form.reference_number"
            type="text"
            placeholder="Optional"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
      </div>
      <template #footer>
        <button
          @click="showRecordModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleRecordPayment"
          :disabled="!form.invoice_id || !form.amount || recordLoading"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ recordLoading ? 'Recording...' : 'Record Payment' }}
        </button>
      </template>
    </Modal>
  </div>
</template>
