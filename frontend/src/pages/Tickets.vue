<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import StatusBadge from '../components/common/StatusBadge.vue'
import Modal from '../components/common/Modal.vue'
import { getTickets, createTicket } from '../api/tickets'
import { getCustomers } from '../api/customers'
import type { TicketType } from '../api/tickets'
import type { Customer } from '../api/customers'
import SkeletonTable from '../components/SkeletonTable.vue'
import EmptyState from '../components/EmptyState.vue'

const router = useRouter()

function delayHideDropdown() {
  setTimeout(() => { showCustomerDropdown.value = false }, 200)
}

const tickets = ref<TicketType[]>([])
const customers = ref<Customer[]>([])
const loading = ref(false)
const saving = ref(false)

const filterStatus = ref('')
const filterPriority = ref('')

const showModal = ref(false)
const customerSearch = ref('')
const filteredCustomers = ref<Customer[]>([])
const showCustomerDropdown = ref(false)

const form = ref({
  customer_id: '',
  customer_name: '',
  subject: '',
  priority: 'medium',
  message: '',
})

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

const priorityOptions = [
  { value: '', label: 'All Priorities' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

async function loadTickets() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterPriority.value) params.priority = filterPriority.value
    const res = await getTickets(params)
    tickets.value = res.data
  } catch (e) {
    console.error('Failed to load tickets:', e)
  } finally {
    loading.value = false
  }
}

async function loadCustomers() {
  try {
    const res = await getCustomers({ page_size: 1000 })
    customers.value = res.data.items
  } catch (e) {
    console.error('Failed to load customers:', e)
  }
}

watch([filterStatus, filterPriority], () => {
  loadTickets()
})

watch(customerSearch, (val) => {
  if (!val.trim()) {
    filteredCustomers.value = []
    return
  }
  const q = val.toLowerCase()
  filteredCustomers.value = customers.value
    .filter((c) => c.full_name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q))
    .slice(0, 10)
})

function selectCustomer(customer: Customer) {
  form.value.customer_id = customer.id
  form.value.customer_name = customer.full_name
  customerSearch.value = customer.full_name
  showCustomerDropdown.value = false
}

function openNewTicket() {
  form.value = { customer_id: '', customer_name: '', subject: '', priority: 'medium', message: '' }
  customerSearch.value = ''
  showModal.value = true
}

async function handleCreate() {
  if (!form.value.customer_id || !form.value.subject.trim() || !form.value.message.trim()) return
  saving.value = true
  try {
    await createTicket({
      customer_id: form.value.customer_id,
      subject: form.value.subject.trim(),
      priority: form.value.priority,
      message: form.value.message.trim(),
    })
    showModal.value = false
    await loadTickets()
  } catch (e) {
    console.error('Failed to create ticket:', e)
  } finally {
    saving.value = false
  }
}

function goToTicket(ticket: TicketType) {
  router.push(`/tickets/${ticket.id}`)
}

onMounted(() => {
  loadTickets()
  loadCustomers()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Support Tickets</h1>
        <p class="text-sm text-gray-500 mt-1">Track and manage customer support requests</p>
      </div>
      <button
        @click="openNewTicket"
        class="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors"
      >
        <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        New Ticket
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3">
      <select
        v-model="filterStatus"
        class="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
      >
        <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
      <select
        v-model="filterPriority"
        class="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
      >
        <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">ID</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Customer</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Subject</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Status</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Priority</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Assigned To</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Created</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <template v-if="loading">
              <tr><td :colspan="7" class="p-0"><SkeletonTable :cols="7" :rows="5" /></td></tr>
            </template>
            <tr v-else-if="!tickets.length">
              <td colspan="7">
                <EmptyState
                  icon="ticket"
                  title="No support tickets"
                  description="Customer support tickets will appear here when submitted through the portal."
                  :actions="[]"
                />
              </td>
            </tr>
            <tr
              v-else
              v-for="ticket in tickets"
              :key="ticket.id"
              @click="goToTicket(ticket)"
              class="hover:bg-gray-50/50 transition-colors cursor-pointer"
            >
              <td class="px-4 py-3 text-sm font-mono text-gray-500">{{ ticket.id.substring(0, 8) }}</td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900">{{ ticket.customer_name || '-' }}</td>
              <td class="px-4 py-3 text-sm text-gray-700">{{ ticket.subject }}</td>
              <td class="px-4 py-3"><StatusBadge :status="ticket.status" /></td>
              <td class="px-4 py-3"><StatusBadge :status="ticket.priority" /></td>
              <td class="px-4 py-3 text-sm text-gray-600">{{ ticket.assigned_to_name || (ticket.assigned_to ? '...' : '-') }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ dayjs(ticket.created_at).format('MMM D, YYYY h:mm A') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- New Ticket Modal -->
    <Modal :open="showModal" title="New Ticket" size="lg" @close="showModal = false">
      <form @submit.prevent="handleCreate" class="space-y-4">
        <!-- Customer Search -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Customer</label>
          <div class="relative">
            <input
              v-model="customerSearch"
              type="text"
              placeholder="Search customer by name or email..."
              @focus="showCustomerDropdown = true"
              @blur="delayHideDropdown"
              class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
            <div
              v-if="showCustomerDropdown && filteredCustomers.length"
              class="absolute z-10 mt-1 w-full bg-white rounded-lg border border-gray-200 shadow-lg max-h-48 overflow-y-auto"
            >
              <button
                v-for="c in filteredCustomers"
                :key="c.id"
                type="button"
                @mousedown.prevent="selectCustomer(c)"
                class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 transition-colors"
              >
                <div class="font-medium text-gray-900">{{ c.full_name }}</div>
                <div class="text-xs text-gray-500">{{ c.email }}</div>
              </button>
            </div>
          </div>
          <p v-if="form.customer_id" class="mt-1 text-xs text-green-600">Selected: {{ form.customer_name }}</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Subject</label>
          <input
            v-model="form.subject"
            type="text"
            required
            placeholder="Brief description of the issue"
            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Priority</label>
          <select
            v-model="form.priority"
            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Message</label>
          <textarea
            v-model="form.message"
            required
            rows="4"
            placeholder="Describe the issue in detail..."
            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
          />
        </div>
      </form>
      <template #footer>
        <button
          @click="showModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
        <button
          @click="handleCreate"
          :disabled="saving || !form.customer_id || !form.subject.trim() || !form.message.trim()"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ saving ? 'Creating...' : 'Create Ticket' }}
        </button>
      </template>
    </Modal>
  </div>
</template>
