<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getActiveSessions, getNetworkStatus, type PppoeSession, type NetworkStatus } from '../api/network'

const sessions = ref<PppoeSession[]>([])
const status = ref<NetworkStatus | null>(null)
const loading = ref(false)
const lastRefresh = ref<Date | null>(null)

let refreshInterval: ReturnType<typeof setInterval> | null = null

async function loadData() {
  loading.value = true
  try {
    const [sessRes, statRes] = await Promise.all([
      getActiveSessions(),
      getNetworkStatus(),
    ])
    const raw = sessRes.data as any
    sessions.value = raw.sessions || raw
    status.value = statRes.data
    lastRefresh.value = new Date()
  } catch (e) {
    console.error('Failed to load active sessions', e)
  } finally {
    loading.value = false
  }
}

function formatTime(date: Date) {
  return date.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(() => {
  loadData()
  refreshInterval = setInterval(loadData, 15000)
})

onBeforeUnmount(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div class="flex items-center gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Active PPPoE Sessions</h1>
          <p class="text-sm text-gray-500 mt-1">Real-time view of connected subscribers</p>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <!-- Connection Status -->
        <div class="flex items-center gap-2">
          <span
            v-if="status"
            :class="[
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium',
              status.connected ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            ]"
          >
            <span :class="['w-2 h-2 rounded-full', status.connected ? 'bg-green-500 animate-pulse' : 'bg-red-500']" />
            {{ status.connected ? 'Connected' : 'Disconnected' }}
          </span>
        </div>

        <!-- Session Count -->
        <div class="rounded-lg bg-white shadow-sm border border-gray-100 px-4 py-2 flex items-center gap-2">
          <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"/></svg>
          <span class="text-sm font-semibold text-gray-900 tabular-nums">{{ sessions.length }}</span>
          <span class="text-xs text-gray-500">sessions</span>
        </div>

        <!-- Auto-refresh indicator -->
        <div class="flex items-center gap-1.5 text-xs text-gray-400">
          <svg :class="['w-3.5 h-3.5', loading ? 'animate-spin text-primary' : '']" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg>
          <span v-if="lastRefresh">{{ formatTime(lastRefresh) }}</span>
        </div>
      </div>
    </div>

    <!-- Router Info Bar -->
    <div v-if="status && status.connected" class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
      <div class="flex flex-wrap items-center gap-6 text-sm">
        <div class="flex items-center gap-2">
          <span class="text-gray-500">Identity:</span>
          <span class="font-medium text-gray-900">{{ status.identity }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-gray-500">Uptime:</span>
          <span class="font-medium text-gray-900">{{ status.uptime }}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-gray-500">CPU:</span>
          <div class="flex items-center gap-2">
            <div class="w-24 h-2 rounded-full bg-gray-200 overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="status.cpu_load > 80 ? 'bg-red-500' : status.cpu_load > 50 ? 'bg-amber-500' : 'bg-green-500'"
                :style="{ width: status.cpu_load + '%' }"
              />
            </div>
            <span class="font-medium text-gray-900 tabular-nums">{{ status.cpu_load }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead>
            <tr class="border-b border-gray-100 bg-gray-50/50">
              <th class="px-4 py-3 font-medium text-gray-500">#</th>
              <th class="px-4 py-3 font-medium text-gray-500">Username</th>
              <th class="px-4 py-3 font-medium text-gray-500">IP Address</th>
              <th class="px-4 py-3 font-medium text-gray-500">MAC (Caller ID)</th>
              <th class="px-4 py-3 font-medium text-gray-500">Service</th>
              <th class="px-4 py-3 font-medium text-gray-500">Uptime</th>
            </tr>
          </thead>
          <tbody v-if="loading && sessions.length === 0">
            <tr>
              <td colspan="6" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                Loading sessions...
              </td>
            </tr>
          </tbody>
          <tbody v-else-if="sessions.length === 0">
            <tr>
              <td colspan="6" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-10 h-10 mx-auto mb-2 text-gray-300" viewBox="0 0 20 20" fill="currentColor"><path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v1h8v-1zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-1a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 17v1h-3zM4.75 14.094A5.973 5.973 0 004 17v1H1v-1a3 3 0 013.75-2.906z"/></svg>
                No active sessions found.
              </td>
            </tr>
          </tbody>
          <tbody v-else>
            <tr v-for="(s, i) in sessions" :key="s['.id']" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
              <td class="px-4 py-3 text-gray-400 tabular-nums">{{ i + 1 }}</td>
              <td class="px-4 py-3">
                <span class="font-medium text-gray-900">{{ s.name }}</span>
              </td>
              <td class="px-4 py-3">
                <code class="text-sm font-mono text-gray-700">{{ s.address }}</code>
              </td>
              <td class="px-4 py-3">
                <code class="text-sm font-mono text-gray-500">{{ s['caller-id'] }}</code>
              </td>
              <td class="px-4 py-3 text-gray-700">{{ s.service }}</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center gap-1 text-gray-700">
                  <svg class="w-3.5 h-3.5 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg>
                  {{ s.uptime }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Footer with count -->
      <div class="px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
        {{ sessions.length }} active session{{ sessions.length !== 1 ? 's' : '' }}
        <span v-if="loading" class="ml-2 text-primary">Refreshing...</span>
      </div>
    </div>
  </div>
</template>
