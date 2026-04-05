<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import Modal from '../components/common/Modal.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import {
  getRouters,
  createRouter,
  updateRouter,
  deleteRouter,
  getRouterStatus,
  importFromRouter,
  vpnSetup,
  vpnActivate,
  type RouterType,
  type RouterStatus,
  type VpnSetupResponse,
} from '../api/routers'
import { scanNetwork } from '../api/network'

const routers = ref<RouterType[]>([])
const loading = ref(false)

// Add/Edit modal
const showModal = ref(false)
const editingRouter = ref<RouterType | null>(null)
const saving = ref(false)
const form = reactive({
  name: '',
  url: '',
  username: 'admin',
  password: '',
  location: '',
  is_active: true,
  maintenance_mode: false,
  maintenance_message: '',
})

// Delete confirm
const confirmDeleteOpen = ref(false)
const deletingId = ref('')
const deleting = ref(false)

// Status modal
const showStatusModal = ref(false)
const statusData = ref<RouterStatus | null>(null)
const loadingStatus = ref(false)

// Import confirm
const confirmImportOpen = ref(false)
const importingId = ref('')
const importingName = ref('')
const importing = ref(false)
const importResult = ref('')

// Scan modal
const showScanModal = ref(false)
const scanSubnet = ref('192.168.88.0/24')
const scanning = ref(false)
const scanResults = ref<Array<{ ip: string; mac?: string; hostname?: string; open_ports?: number[] }>>([])

// VPN Setup
const showVpnModal = ref(false)
const vpnStep = ref<1 | 2 | 3>(1)
const vpnLoading = ref(false)
const vpnRouterId = ref('')
const vpnRouterName = ref('')
const vpnData = ref<VpnSetupResponse | null>(null)
const vpnClientKey = ref('')
const vpnClientLan = ref('')
const vpnError = ref('')
const vpnSuccess = ref('')
const vpnCopied = ref(false)

async function startVpnSetup(router: RouterType) {
  vpnRouterId.value = router.id
  vpnRouterName.value = router.name
  vpnStep.value = 1
  vpnData.value = null
  vpnClientKey.value = ''
  vpnClientLan.value = ''
  vpnError.value = ''
  vpnSuccess.value = ''
  vpnCopied.value = false
  showVpnModal.value = true
  vpnLoading.value = true
  try {
    const { data } = await vpnSetup(router.id)
    vpnData.value = data
  } catch (e: any) {
    vpnError.value = e.response?.data?.detail || 'Failed to generate VPN setup'
  } finally {
    vpnLoading.value = false
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
    vpnError.value = 'Please paste your MikroTik public key'
    return
  }
  vpnError.value = ''
  vpnLoading.value = true
  try {
    const { data } = await vpnActivate(vpnRouterId.value, {
      public_key: vpnClientKey.value.trim(),
      client_lan: vpnClientLan.value.trim(),
    })
    vpnSuccess.value = data.message
    vpnStep.value = 3
    await loadRouters()
  } catch (e: any) {
    vpnError.value = e.response?.data?.detail || 'Failed to activate VPN'
  } finally {
    vpnLoading.value = false
  }
}

async function loadRouters() {
  loading.value = true
  try {
    const { data } = await getRouters()
    routers.value = data
  } catch (e) {
    console.error('Failed to load routers', e)
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editingRouter.value = null
  form.name = ''
  form.url = ''
  form.username = 'admin'
  form.password = ''
  form.location = ''
  form.is_active = true
  form.maintenance_mode = false
  form.maintenance_message = ''
  showModal.value = true
}

function openEdit(router: RouterType) {
  editingRouter.value = router
  form.name = router.name
  form.url = router.url
  form.username = router.username
  form.password = ''
  form.location = router.location || ''
  form.is_active = router.is_active
  form.maintenance_mode = router.maintenance_mode
  form.maintenance_message = router.maintenance_message || ''
  showModal.value = true
}

async function saveRouter() {
  saving.value = true
  try {
    const payload: Record<string, any> = {
      name: form.name,
      url: form.url,
      username: form.username,
      location: form.location || null,
      is_active: form.is_active,
      maintenance_mode: form.maintenance_mode,
      maintenance_message: form.maintenance_message || null,
    }
    if (form.password) payload.password = form.password
    if (editingRouter.value) {
      await updateRouter(editingRouter.value.id, payload)
    } else {
      payload.password = form.password
      await createRouter(payload)
    }
    showModal.value = false
    await loadRouters()
  } catch (e) {
    console.error('Failed to save router', e)
  } finally {
    saving.value = false
  }
}

function askDelete(id: string) {
  deletingId.value = id
  confirmDeleteOpen.value = true
}

async function doDelete() {
  deleting.value = true
  try {
    await deleteRouter(deletingId.value)
    confirmDeleteOpen.value = false
    await loadRouters()
  } catch (e) {
    console.error('Failed to delete router', e)
  } finally {
    deleting.value = false
  }
}

async function viewStatus(router: RouterType) {
  statusData.value = null
  loadingStatus.value = true
  showStatusModal.value = true
  try {
    const { data } = await getRouterStatus(router.id)
    statusData.value = data
  } catch (e) {
    console.error('Failed to get router status', e)
    statusData.value = {
      id: router.id,
      name: router.name,
      connected: false,
      error: 'Failed to connect to router',
    }
  } finally {
    loadingStatus.value = false
  }
}

function askImport(router: RouterType) {
  importingId.value = router.id
  importingName.value = router.name
  importResult.value = ''
  confirmImportOpen.value = true
}

async function doImport() {
  importing.value = true
  importResult.value = ''
  try {
    const { data } = await importFromRouter(importingId.value)
    importResult.value = typeof data === 'string' ? data : (data as any)?.message || 'Import completed successfully.'
    confirmImportOpen.value = false
    await loadRouters()
  } catch (e: any) {
    importResult.value = e.response?.data?.detail || 'Import failed.'
  } finally {
    importing.value = false
  }
}

async function doScan() {
  scanning.value = true
  scanResults.value = []
  try {
    const { data } = await scanNetwork({ subnet: scanSubnet.value, timeout: 10 })
    scanResults.value = data as any[]
  } catch (e) {
    console.error('Failed to scan network', e)
  } finally {
    scanning.value = false
  }
}

function memoryPercent(status: RouterStatus): number {
  if (!status.total_memory || !status.free_memory) return 0
  return Math.round(((status.total_memory - status.free_memory) / status.total_memory) * 100)
}

function formatMemory(bytes: number | undefined): string {
  if (!bytes) return '---'
  return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
}

onMounted(loadRouters)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Routers</h1>
        <p class="text-sm text-gray-500 mt-1">Manage MikroTik routers and network devices</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="showScanModal = true"
          class="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-gray-300 rounded-lg text-gray-700 bg-white hover:bg-gray-50 transition-colors"
        >
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z" clip-rule="evenodd"/></svg>
          Scan Network
        </button>
        <button
          @click="openAdd"
          class="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors"
        >
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          Add Router
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead>
            <tr class="border-b border-gray-100 bg-gray-50/50">
              <th class="px-4 py-3 font-medium text-gray-500">Name</th>
              <th class="px-4 py-3 font-medium text-gray-500">URL</th>
              <th class="px-4 py-3 font-medium text-gray-500">Location</th>
              <th class="px-4 py-3 font-medium text-gray-500">Status</th>
              <th class="px-4 py-3 font-medium text-gray-500">Maintenance</th>
              <th class="px-4 py-3 font-medium text-gray-500 text-right">Actions</th>
            </tr>
          </thead>
          <tbody v-if="loading">
            <tr>
              <td colspan="6" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                Loading routers...
              </td>
            </tr>
          </tbody>
          <tbody v-else-if="routers.length === 0">
            <tr>
              <td colspan="6" class="px-4 py-12 text-center text-gray-400">No routers configured. Add your first router to get started.</td>
            </tr>
          </tbody>
          <tbody v-else>
            <tr v-for="r in routers" :key="r.id" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
              <td class="px-4 py-3">
                <div class="font-medium text-gray-900">{{ r.name }}</div>
                <div class="text-xs text-gray-400">{{ r.username }}@{{ r.url }}</div>
              </td>
              <td class="px-4 py-3">
                <code class="text-sm font-mono text-gray-700">{{ r.url }}</code>
              </td>
              <td class="px-4 py-3 text-gray-700">{{ r.location || '---' }}</td>
              <td class="px-4 py-3">
                <StatusBadge :status="r.is_active ? 'active' : 'disconnected'" />
              </td>
              <td class="px-4 py-3">
                <span
                  v-if="r.maintenance_mode"
                  class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700"
                >
                  <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
                  Maintenance
                </span>
                <span v-else class="text-gray-400 text-xs">---</span>
              </td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button @click="viewStatus(r)" class="text-xs font-medium text-blue-600 hover:text-blue-700 transition-colors">Status</button>
                  <button @click="askImport(r)" class="text-xs font-medium text-green-600 hover:text-green-700 transition-colors">Import</button>
                  <button @click="startVpnSetup(r)" class="text-xs font-medium text-purple-600 hover:text-purple-700 transition-colors">VPN</button>
                  <button @click="openEdit(r)" class="text-xs font-medium text-primary hover:text-primary-hover transition-colors">Edit</button>
                  <button @click="askDelete(r.id)" class="text-xs font-medium text-red-600 hover:text-red-700 transition-colors">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="px-4 py-3 border-t border-gray-100 text-sm text-gray-500">
        {{ routers.length }} router{{ routers.length !== 1 ? 's' : '' }}
      </div>
    </div>

    <!-- Add/Edit Modal -->
    <Modal :open="showModal" :title="editingRouter ? 'Edit Router' : 'Add Router'" size="lg" @close="showModal = false">
      <form @submit.prevent="saveRouter" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Name</label>
            <input
              v-model="form.name"
              type="text"
              required
              placeholder="e.g. Main Router"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">URL</label>
            <input
              v-model="form.url"
              type="text"
              required
              placeholder="e.g. 192.168.88.1"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors font-mono"
            />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
            <input
              v-model="form.username"
              type="text"
              required
              placeholder="admin"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">
              Password
              <span v-if="editingRouter" class="text-gray-400 font-normal">(leave blank to keep current)</span>
            </label>
            <input
              v-model="form.password"
              type="password"
              :required="!editingRouter"
              placeholder="••••••••"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Location</label>
          <input
            v-model="form.location"
            type="text"
            placeholder="e.g. Server Room, Building A"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          />
        </div>
        <div class="flex flex-wrap gap-6 pt-2">
          <label class="flex items-center gap-3 cursor-pointer">
            <div class="relative">
              <input v-model="form.is_active" type="checkbox" class="sr-only peer" />
              <div class="w-10 h-6 rounded-full bg-gray-200 peer-checked:bg-primary transition-colors" />
              <div class="absolute left-0.5 top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
            </div>
            <span class="text-sm font-medium text-gray-700">Active</span>
          </label>
          <label class="flex items-center gap-3 cursor-pointer">
            <div class="relative">
              <input v-model="form.maintenance_mode" type="checkbox" class="sr-only peer" />
              <div class="w-10 h-6 rounded-full bg-gray-200 peer-checked:bg-amber-500 transition-colors" />
              <div class="absolute left-0.5 top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
            </div>
            <span class="text-sm font-medium text-gray-700">Maintenance Mode</span>
          </label>
        </div>
        <div v-if="form.maintenance_mode">
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Maintenance Message</label>
          <textarea
            v-model="form.maintenance_message"
            rows="2"
            placeholder="Reason for maintenance..."
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
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
          @click="saveRouter"
          :disabled="saving || !form.name || !form.url"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
        >
          {{ saving ? 'Saving...' : editingRouter ? 'Update' : 'Add Router' }}
        </button>
      </template>
    </Modal>

    <!-- Status Modal -->
    <Modal :open="showStatusModal" title="Router Status" size="lg" @close="showStatusModal = false">
      <div v-if="loadingStatus" class="flex items-center justify-center py-12">
        <svg class="w-8 h-8 animate-spin text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="statusData" class="space-y-6">
        <!-- Connection header -->
        <div class="flex items-center gap-3">
          <span
            :class="[
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium',
              statusData.connected ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            ]"
          >
            <span :class="['w-2 h-2 rounded-full', statusData.connected ? 'bg-green-500' : 'bg-red-500']" />
            {{ statusData.connected ? 'Connected' : 'Disconnected' }}
          </span>
          <span v-if="statusData.identity" class="text-lg font-semibold text-gray-900">{{ statusData.identity }}</span>
        </div>

        <div v-if="statusData.error" class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {{ statusData.error }}
        </div>

        <div v-if="statusData.connected" class="grid grid-cols-2 gap-4">
          <!-- Uptime -->
          <div class="rounded-lg bg-gray-50 p-4">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Uptime</p>
            <p class="text-lg font-semibold text-gray-900">{{ statusData.uptime || '---' }}</p>
          </div>
          <!-- Version -->
          <div class="rounded-lg bg-gray-50 p-4">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">RouterOS Version</p>
            <p class="text-lg font-semibold text-gray-900">{{ statusData.version || '---' }}</p>
          </div>
          <!-- Active Sessions -->
          <div class="rounded-lg bg-gray-50 p-4">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Active Sessions</p>
            <p class="text-lg font-semibold text-gray-900 tabular-nums">{{ statusData.active_sessions ?? '---' }}</p>
          </div>
          <!-- CPU Load -->
          <div class="rounded-lg bg-gray-50 p-4">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">CPU Load</p>
            <div class="flex items-center gap-3 mt-1">
              <div class="flex-1 h-3 rounded-full bg-gray-200 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="(statusData.cpu_load ?? 0) > 80 ? 'bg-red-500' : (statusData.cpu_load ?? 0) > 50 ? 'bg-amber-500' : 'bg-green-500'"
                  :style="{ width: (statusData.cpu_load ?? 0) + '%' }"
                />
              </div>
              <span class="text-lg font-semibold text-gray-900 tabular-nums">{{ statusData.cpu_load ?? 0 }}%</span>
            </div>
          </div>
          <!-- Memory -->
          <div class="rounded-lg bg-gray-50 p-4 col-span-2">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Memory Usage</p>
            <div class="flex items-center gap-3 mt-1">
              <div class="flex-1 h-3 rounded-full bg-gray-200 overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="memoryPercent(statusData) > 80 ? 'bg-red-500' : memoryPercent(statusData) > 50 ? 'bg-amber-500' : 'bg-blue-500'"
                  :style="{ width: memoryPercent(statusData) + '%' }"
                />
              </div>
              <span class="text-lg font-semibold text-gray-900 tabular-nums">{{ memoryPercent(statusData) }}%</span>
            </div>
            <p class="text-xs text-gray-500 mt-1">
              {{ formatMemory((statusData.total_memory ?? 0) - (statusData.free_memory ?? 0)) }} used / {{ formatMemory(statusData.total_memory) }} total
            </p>
          </div>
        </div>
      </div>
      <template #footer>
        <button
          @click="showStatusModal = false"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
        >
          Close
        </button>
      </template>
    </Modal>

    <!-- Scan Network Modal -->
    <Modal :open="showScanModal" title="Scan Network" size="lg" @close="showScanModal = false">
      <div class="space-y-4">
        <div class="flex items-end gap-3">
          <div class="flex-1">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Subnet</label>
            <input
              v-model="scanSubnet"
              type="text"
              placeholder="192.168.88.0/24"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
            />
          </div>
          <button
            @click="doScan"
            :disabled="scanning || !scanSubnet"
            class="px-4 py-2.5 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50 inline-flex items-center gap-2"
          >
            <svg v-if="scanning" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
            {{ scanning ? 'Scanning...' : 'Scan' }}
          </button>
        </div>

        <div v-if="scanResults.length > 0" class="overflow-x-auto">
          <table class="w-full text-sm text-left">
            <thead>
              <tr class="border-b border-gray-100 bg-gray-50/50">
                <th class="px-4 py-2 font-medium text-gray-500">IP Address</th>
                <th class="px-4 py-2 font-medium text-gray-500">MAC Address</th>
                <th class="px-4 py-2 font-medium text-gray-500">Hostname</th>
                <th class="px-4 py-2 font-medium text-gray-500">Open Ports</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in scanResults" :key="i" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="px-4 py-2"><code class="font-mono text-gray-800">{{ r.ip }}</code></td>
                <td class="px-4 py-2"><code class="font-mono text-gray-500">{{ r.mac || '---' }}</code></td>
                <td class="px-4 py-2 text-gray-700">{{ r.hostname || '---' }}</td>
                <td class="px-4 py-2">
                  <div class="flex gap-1 flex-wrap">
                    <span
                      v-for="port in (r.open_ports || [])"
                      :key="port"
                      class="inline-flex px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-xs font-mono"
                    >
                      {{ port }}
                    </span>
                    <span v-if="!r.open_ports?.length" class="text-gray-400">---</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="text-xs text-gray-500 mt-2 px-4">{{ scanResults.length }} device{{ scanResults.length !== 1 ? 's' : '' }} found</p>
        </div>

        <div v-else-if="!scanning" class="text-center py-6 text-gray-400 text-sm">
          Enter a subnet and click Scan to discover devices on the network.
        </div>
      </div>
      <template #footer>
        <button
          @click="showScanModal = false"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Close
        </button>
      </template>
    </Modal>

    <!-- VPN Setup Modal -->
    <Modal :open="showVpnModal" :title="'VPN Setup \u2014 ' + vpnRouterName" size="lg" @close="showVpnModal = false">
      <div class="space-y-4">
        <!-- Steps indicator -->
        <div class="flex items-center gap-2 text-xs font-medium">
          <span :class="vpnStep >= 1 ? 'text-primary' : 'text-gray-400'">1. Copy Script</span>
          <svg class="w-4 h-4 text-gray-300" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/></svg>
          <span :class="vpnStep >= 2 ? 'text-primary' : 'text-gray-400'">2. Enter Key</span>
          <svg class="w-4 h-4 text-gray-300" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd"/></svg>
          <span :class="vpnStep >= 3 ? 'text-primary' : 'text-gray-400'">3. Connected</span>
        </div>

        <!-- Loading -->
        <div v-if="vpnLoading && !vpnData" class="flex items-center justify-center py-8">
          <svg class="w-8 h-8 animate-spin text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
        </div>

        <!-- Step 1: Copy Script -->
        <div v-if="vpnStep === 1 && vpnData">
          <p class="text-sm text-gray-600 mb-3">Paste this script into your MikroTik terminal (Winbox Terminal tab or SSH):</p>
          <div class="relative rounded-xl bg-gray-900 p-4 overflow-x-auto">
            <pre class="text-sm text-green-400 font-mono whitespace-pre">{{ vpnData.script }}</pre>
            <button @click="copyVpnScript" class="absolute top-2 right-2 px-2.5 py-1 text-xs rounded-lg transition-colors" :class="vpnCopied ? 'bg-green-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'">
              {{ vpnCopied ? 'Copied!' : 'Copy' }}
            </button>
          </div>
          <div class="mt-3 rounded-lg bg-blue-50 border border-blue-200 p-3">
            <p class="text-sm text-blue-700">After pasting, run <code class="bg-blue-100 px-1 rounded">/interface/wireguard/print</code> and copy the <strong>Public Key</strong> shown.</p>
          </div>
        </div>

        <!-- Step 2: Enter Public Key -->
        <div v-if="vpnStep === 2">
          <p class="text-sm text-gray-600 mb-3">Paste the <strong>Public Key</strong> from your MikroTik WireGuard interface:</p>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">MikroTik Public Key</label>
            <input v-model="vpnClientKey" type="text" placeholder="e.g. VSs6joEGtYn6ZQJJiqSepzR+H3xK82f37H1EqUUeE2k=" class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
          <div class="mt-3">
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Router LAN Subnet <span class="text-gray-400 font-normal">(optional — e.g. 192.168.1.0/24)</span></label>
            <input v-model="vpnClientLan" type="text" placeholder="192.168.1.0/24" class="w-full px-3 py-2.5 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary" />
          </div>
        </div>

        <!-- Step 3: Connected -->
        <div v-if="vpnStep === 3">
          <div class="rounded-lg bg-green-50 border border-green-200 p-4 text-center">
            <svg class="w-12 h-12 text-green-500 mx-auto mb-2" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"/></svg>
            <p class="text-lg font-semibold text-green-800">VPN Tunnel Activated!</p>
            <p class="text-sm text-green-700 mt-1">{{ vpnSuccess }}</p>
            <p class="text-sm text-gray-600 mt-2">Your router URL has been updated to <code class="bg-green-100 px-1.5 py-0.5 rounded font-mono text-green-800">http://{{ vpnData?.tunnel_ip }}</code></p>
          </div>
        </div>

        <!-- Error -->
        <div v-if="vpnError" class="rounded-lg bg-red-50 border border-red-200 p-3">
          <p class="text-sm text-red-700">{{ vpnError }}</p>
        </div>
      </div>

      <template #footer>
        <button @click="showVpnModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
          {{ vpnStep === 3 ? 'Done' : 'Cancel' }}
        </button>
        <button v-if="vpnStep === 1 && vpnData" @click="vpnStep = 2; vpnError = ''" class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover">
          Next — I've pasted the script
        </button>
        <button v-if="vpnStep === 2" @click="activateVpn" :disabled="vpnLoading || !vpnClientKey.trim()" class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover disabled:opacity-50">
          {{ vpnLoading ? 'Activating...' : 'Activate VPN' }}
        </button>
      </template>
    </Modal>

    <!-- Confirm Delete -->
    <ConfirmDialog
      :open="confirmDeleteOpen"
      title="Delete Router"
      message="Are you sure you want to delete this router? All associated data will be permanently removed."
      confirm-text="Delete"
      :danger="true"
      :loading="deleting"
      @confirm="doDelete"
      @cancel="confirmDeleteOpen = false"
    />

    <!-- Confirm Import -->
    <ConfirmDialog
      :open="confirmImportOpen"
      :title="'Import from ' + importingName"
      message="This will import all PPPoE users and secrets from this router. Existing users with matching usernames will be updated. Continue?"
      confirm-text="Import"
      :loading="importing"
      @confirm="doImport"
      @cancel="confirmImportOpen = false"
    />
  </div>
</template>
