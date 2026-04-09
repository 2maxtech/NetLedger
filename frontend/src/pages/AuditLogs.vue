<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getAuditLogs, type AuditLog } from '../api/audit'
import Pagination from '../components/common/Pagination.vue'

const logs = ref<AuditLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// Filters
const filterEntityType = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

// Expanded rows
const expandedRows = ref<Set<string>>(new Set())

const entityTypes = [
  { value: '', label: 'All Types' },
  { value: 'customer', label: 'Customer' },
  { value: 'invoice', label: 'Invoice' },
  { value: 'payment', label: 'Payment' },
  { value: 'plan', label: 'Plan' },
  { value: 'router', label: 'Router' },
  { value: 'ticket', label: 'Ticket' },
  { value: 'voucher', label: 'Voucher' },
  { value: 'user', label: 'User' },
  { value: 'expense', label: 'Expense' },
]

async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: page.value, page_size: pageSize }
    if (filterEntityType.value) params.entity_type = filterEntityType.value
    if (filterDateFrom.value) params.date_from = filterDateFrom.value
    if (filterDateTo.value) params.date_to = filterDateTo.value
    const { data } = await getAuditLogs(params)
    if (Array.isArray(data)) {
      logs.value = data
      total.value = data.length
    } else {
      logs.value = data.items
      total.value = data.total
    }
  } catch (e) {
    console.error('Failed to fetch audit logs', e)
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  fetchLogs()
}

function toggleRow(id: string) {
  if (expandedRows.value.has(id)) {
    expandedRows.value.delete(id)
  } else {
    expandedRows.value.add(id)
  }
}

function shortId(id: string | null) {
  if (!id) return '-'
  return id.substring(0, 8)
}

watch(page, fetchLogs)
onMounted(fetchLogs)
</script>

<template>
  <div class="space-y-6">
    <h1 class="text-2xl font-bold text-gray-900">Audit Logs</h1>

    <!-- Filters -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
      <div class="flex flex-wrap items-end gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Entity Type</label>
          <select
            v-model="filterEntityType"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option v-for="et in entityTypes" :key="et.value" :value="et.value">{{ et.label }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">From</label>
          <input
            v-model="filterDateFrom"
            type="date"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">To</label>
          <input
            v-model="filterDateTo"
            type="date"
            class="rounded-lg border border-gray-300 text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <button
          @click="applyFilters"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
        >
          Filter
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left w-8"></th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Timestamp</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">User</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Action</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Entity Type</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Entity ID</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">IP Address</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <!-- Loading -->
            <template v-if="loading">
              <tr v-for="i in 5" :key="i">
                <td v-for="j in 7" :key="j" class="px-4 py-3">
                  <div class="h-4 bg-gray-100 rounded animate-pulse" />
                </td>
              </tr>
            </template>
            <!-- Empty -->
            <tr v-else-if="!logs.length">
              <td colspan="7" class="px-4 py-12 text-center text-gray-400">No audit logs found</td>
            </tr>
            <!-- Rows -->
            <template v-else v-for="log in logs" :key="log.id">
              <tr
                @click="toggleRow(log.id)"
                class="hover:bg-gray-50/50 transition-colors cursor-pointer"
              >
                <td class="px-4 py-3 text-sm text-gray-400">
                  <svg
                    :class="['w-4 h-4 transition-transform', expandedRows.has(log.id) ? 'rotate-90' : '']"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
                  </svg>
                </td>
                <td class="px-4 py-3 text-sm text-gray-700">{{ dayjs(log.created_at).format('MMM D, YYYY h:mm A') }}</td>
                <td class="px-4 py-3 text-sm text-gray-700">{{ log.user_name || shortId(log.user_id) }}</td>
                <td class="px-4 py-3 text-sm text-gray-700 font-medium">{{ log.action }}</td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                    {{ log.entity_type }}
                  </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-500 font-mono">{{ shortId(log.entity_id) }}</td>
                <td class="px-4 py-3 text-sm text-gray-500">{{ log.ip_address || '-' }}</td>
              </tr>
              <!-- Expanded Details -->
              <tr v-if="expandedRows.has(log.id)">
                <td colspan="7" class="px-4 py-4 bg-gray-50">
                  <div class="text-xs font-medium text-gray-500 uppercase mb-2">Details</div>
                  <pre class="text-sm text-gray-700 bg-white rounded-lg border border-gray-200 p-4 overflow-x-auto whitespace-pre-wrap">{{ log.details ? JSON.stringify(log.details, null, 2) : 'No details' }}</pre>
                </td>
              </tr>
            </template>
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
  </div>
</template>
