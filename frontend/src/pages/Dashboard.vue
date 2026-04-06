<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getDashboard, type DashboardData } from '../api/network'
import { getRouters, getRouterStatus, type RouterType, type RouterStatus } from '../api/routers'
import StatCard from '../components/common/StatCard.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Bar } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

const data = ref<DashboardData | null>(null)
const loading = ref(true)
const error = ref('')

// Multi-router state
const routers = ref<RouterType[]>([])
const routerStatuses = ref<Map<string, RouterStatus & { interfaces?: any[] }>>(new Map())

let interval: ReturnType<typeof setInterval> | null = null

async function fetchRouters() {
  try {
    const { data: list } = await getRouters()
    routers.value = list.filter(r => r.is_active)
    // Fetch status for each router in parallel
    const statusPromises = routers.value.map(async (r) => {
      try {
        const { data: st } = await getRouterStatus(r.id)
        routerStatuses.value.set(r.id, st)
      } catch {
        routerStatuses.value.set(r.id, { id: r.id, name: r.name, connected: false, error: 'Failed to connect' })
      }
    })
    await Promise.all(statusPromises)
  } catch {
    // No routers in DB — that's fine, we still have the default from dashboard
  }
}

async function fetchDashboard() {
  try {
    const [dashRes] = await Promise.all([getDashboard(), fetchRouters()])
    data.value = dashRes.data
    error.value = ''
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load dashboard data.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
  interval = setInterval(fetchDashboard, 5000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})

// Determine what to show: DB routers if any, otherwise default MikroTik from dashboard
const showDbRouters = computed(() => routers.value.length > 0)

function fmt(n: number | undefined): string {
  if (n == null) return '0'
  return n.toLocaleString()
}

function peso(n: number | undefined): string {
  if (n == null) return '\u20B10'
  return '\u20B1' + n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

function memPercent(free: number | undefined, total: number | undefined): number {
  if (!total) return 0
  return Math.round(((total - (free || 0)) / total) * 100)
}

function formatBytes(bytes: number | undefined): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let val = bytes
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024
    i++
  }
  return val.toFixed(i > 1 ? 2 : 0) + ' ' + units[i]
}

function cpuColor(load: number | string | undefined): string {
  const n = Number(load) || 0
  if (n > 80) return 'text-red-600'
  if (n > 50) return 'text-amber-600'
  return 'text-green-600'
}

function cpuBarColor(load: number | string | undefined): string {
  const n = Number(load) || 0
  if (n > 80) return 'bg-red-500'
  if (n > 50) return 'bg-amber-500'
  return 'bg-green-500'
}

function memColor(free: number | undefined, total: number | undefined): string {
  const p = memPercent(free, total)
  if (p > 80) return 'text-red-600'
  if (p > 50) return 'text-amber-600'
  return 'text-green-600'
}

function memBarColor(free: number | undefined, total: number | undefined): string {
  const p = memPercent(free, total)
  if (p > 80) return 'bg-red-500'
  if (p > 50) return 'bg-amber-500'
  return 'bg-green-500'
}

// Chart config
const chartData = computed(() => {
  const trend = data.value?.revenue_trend || []
  return {
    labels: trend.map((r) => r.month),
    datasets: [
      {
        label: 'Collected',
        backgroundColor: '#e8700a',
        borderRadius: 4,
        data: trend.map((r) => r.collected),
      },
    ],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { usePointStyle: true, pointStyle: 'circle', padding: 20, font: { family: 'Inter', size: 12 } },
    },
    tooltip: {
      callbacks: {
        label: (ctx: any) => `${ctx.dataset.label}: \u20B1${ctx.raw?.toLocaleString() || 0}`,
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 } } },
    y: {
      grid: { color: '#f3f4f6' },
      ticks: { font: { family: 'Inter', size: 11 }, callback: (v: any) => `\u20B1${(v / 1000).toFixed(0)}k` },
    },
  },
}

function formatDate(s: string): string {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleDateString('en-PH', { month: 'short', day: 'numeric', year: 'numeric' })
}
</script>

<template>
  <div class="space-y-5">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Dashboard</h1>
      <p class="text-sm text-gray-500 mt-0.5">Real-time overview of your ISP operations</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
    </div>

    <!-- Error -->
    <div v-else-if="error && !data" class="rounded-xl bg-red-50 border border-red-200 p-6 text-center">
      <p class="text-red-700 text-sm">{{ error }}</p>
      <button @click="fetchDashboard" class="mt-3 text-sm font-medium text-primary hover:underline">Retry</button>
    </div>

    <template v-else-if="data">
      <!-- Two-column layout: Left (stats + chart) | Right (routers stacking) -->
      <div class="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <!-- LEFT COLUMN -->
        <div class="xl:col-span-2 space-y-5">
          <!-- Compact stat cards -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
              <p class="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Subscribers</p>
              <p class="text-xl font-bold text-gray-900 mt-1 tabular-nums">{{ fmt(data.subscribers.total) }}</p>
              <p class="text-xs text-green-600 mt-0.5">{{ fmt(data.subscribers.active) }} active</p>
            </div>
            <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
              <p class="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Online Now</p>
              <p class="text-xl font-bold text-gray-900 mt-1 tabular-nums">{{ fmt(data.mikrotik.active_sessions) }}</p>
              <p class="text-xs text-amber-600 mt-0.5">{{ fmt(data.subscribers.suspended) }} suspended</p>
            </div>
            <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
              <p class="text-[11px] font-medium text-gray-400 uppercase tracking-wider">MRR</p>
              <p class="text-xl font-bold text-gray-900 mt-1 tabular-nums">{{ peso(data.billing.mrr) }}</p>
              <p class="text-xs text-blue-600 mt-0.5">{{ peso(data.billing.collected_this_month) }} collected</p>
            </div>
            <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
              <p class="text-[11px] font-medium text-gray-400 uppercase tracking-wider">Overdue</p>
              <p class="text-xl font-bold tabular-nums mt-1" :class="data.billing.overdue_amount > 0 ? 'text-red-600' : 'text-gray-900'">{{ peso(data.billing.overdue_amount) }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ data.billing.overdue_count || 0 }} invoice{{ data.billing.overdue_count !== 1 ? 's' : '' }}</p>
            </div>
          </div>

          <!-- Revenue chart -->
          <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-5">
            <h3 class="text-sm font-semibold text-gray-900 mb-4">Revenue Trend</h3>
            <div class="h-56">
              <Bar v-if="data.revenue_trend?.length" :data="chartData" :options="chartOptions" />
              <div v-else class="flex items-center justify-center h-full text-sm text-gray-400">No revenue data</div>
            </div>
          </div>

          <!-- Recent Payments -->
          <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-5">
            <h3 class="text-sm font-semibold text-gray-900 mb-3">Recent Payments</h3>
            <div v-if="data.recent_payments?.length" class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="border-b border-gray-100">
                    <th class="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Customer</th>
                    <th class="text-right py-2 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                    <th class="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Method</th>
                    <th class="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-50">
                  <tr v-for="p in data.recent_payments.slice(0, 5)" :key="p.id" class="hover:bg-gray-50/50 transition-colors">
                    <td class="py-2 px-3 font-medium text-gray-900">{{ p.customer_name || '—' }}</td>
                    <td class="py-2 px-3 text-right tabular-nums text-gray-900">{{ peso(p.amount) }}</td>
                    <td class="py-2 px-3"><span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 capitalize">{{ p.method }}</span></td>
                    <td class="py-2 px-3 text-gray-500">{{ formatDate(p.received_at) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="text-center py-8 text-sm text-gray-400">No recent payments</div>
          </div>
        </div>

        <!-- RIGHT COLUMN — Router cards stacking vertically -->
        <div class="space-y-4">
          <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">MikroTik Routers</p>
          <div
            v-for="r in routers"
            :key="r.id"
            class="rounded-xl bg-white shadow-sm border border-gray-100 p-4"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-2.5">
                <div class="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                  <svg class="w-4 h-4 text-gray-600" viewBox="0 0 20 20" fill="currentColor"><path d="M4.632 3.533A2 2 0 016.577 2h6.846a2 2 0 011.945 1.533l1.976 8.234A3.489 3.489 0 0016 11.5H4c-.476 0-.93.095-1.344.267l1.976-8.234z"/><path fill-rule="evenodd" d="M4 13a2 2 0 100 4h12a2 2 0 100-4H4zm11.24 2a.75.75 0 01.75-.75H16a.75.75 0 01.75.75v.01a.75.75 0 01-.75.75h-.01a.75.75 0 01-.75-.75V15zm-2.25-.75a.75.75 0 00-.75.75v.01c0 .414.336.75.75.75H13a.75.75 0 00.75-.75V15a.75.75 0 00-.75-.75h-.01z" clip-rule="evenodd"/></svg>
                </div>
                <div>
                  <p class="font-semibold text-gray-900 text-sm leading-tight">{{ r.name }}</p>
                  <p class="text-[10px] text-gray-400">{{ routerStatuses.get(r.id)?.identity || r.url }} <span v-if="routerStatuses.get(r.id)?.version">&middot; v{{ routerStatuses.get(r.id)?.version }}</span></p>
                </div>
              </div>
              <StatusBadge :status="routerStatuses.get(r.id)?.connected ? 'online' : 'disconnected'" />
            </div>

            <template v-if="routerStatuses.get(r.id)?.connected">
              <div class="grid grid-cols-2 gap-3 text-center">
                <div class="rounded-lg bg-gray-50 p-2.5">
                  <p class="text-[10px] font-medium text-gray-400 uppercase">Uptime</p>
                  <p class="text-xs font-semibold text-gray-900 tabular-nums mt-0.5">{{ routerStatuses.get(r.id)?.uptime || '--' }}</p>
                </div>
                <div class="rounded-lg bg-gray-50 p-2.5">
                  <p class="text-[10px] font-medium text-gray-400 uppercase">Sessions</p>
                  <p class="text-xs font-semibold text-gray-900 tabular-nums mt-0.5">{{ fmt(routerStatuses.get(r.id)?.active_sessions) }}</p>
                </div>
              </div>
              <div class="mt-3 space-y-2">
                <div>
                  <div class="flex items-center justify-between">
                    <p class="text-[10px] font-medium text-gray-400 uppercase">CPU</p>
                    <span class="text-[10px] font-semibold tabular-nums" :class="cpuColor(routerStatuses.get(r.id)?.cpu_load)">{{ routerStatuses.get(r.id)?.cpu_load || 0 }}%</span>
                  </div>
                  <div class="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden mt-0.5">
                    <div class="h-full rounded-full transition-all duration-500" :class="cpuBarColor(routerStatuses.get(r.id)?.cpu_load)" :style="{ width: (Number(routerStatuses.get(r.id)?.cpu_load) || 0) + '%' }" />
                  </div>
                </div>
                <div>
                  <div class="flex items-center justify-between">
                    <p class="text-[10px] font-medium text-gray-400 uppercase">Memory</p>
                    <span class="text-[10px] font-semibold tabular-nums" :class="memColor(routerStatuses.get(r.id)?.free_memory, routerStatuses.get(r.id)?.total_memory)">{{ memPercent(routerStatuses.get(r.id)?.free_memory, routerStatuses.get(r.id)?.total_memory) }}%</span>
                  </div>
                  <div class="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden mt-0.5">
                    <div class="h-full rounded-full transition-all duration-500" :class="memBarColor(routerStatuses.get(r.id)?.free_memory, routerStatuses.get(r.id)?.total_memory)" :style="{ width: memPercent(routerStatuses.get(r.id)?.free_memory, routerStatuses.get(r.id)?.total_memory) + '%' }" />
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="text-xs text-gray-400 text-center py-3">
              {{ routerStatuses.get(r.id)?.error || 'Unable to connect' }}
            </div>
          </div>

          <!-- No routers message -->
          <div v-if="!routers.length" class="rounded-xl bg-white shadow-sm border border-gray-100 p-6 text-center">
            <p class="text-sm text-gray-400">No routers configured</p>
            <router-link to="/routers" class="text-xs text-primary hover:underline mt-1 inline-block">Add a router</router-link>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
