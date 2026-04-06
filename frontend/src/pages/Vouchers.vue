<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import Modal from '../components/common/Modal.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import {
  getVouchers,
  generateVouchers,
  getHotspotProfiles,
  revokeVoucher,
  type VoucherType,
  type HotspotProfile,
} from '../api/vouchers'
import { getRouters, type RouterType } from '../api/routers'

const vouchers = ref<VoucherType[]>([])
const routers = ref<RouterType[]>([])
const loading = ref(false)

const filterStatus = ref('')
const STATUSES = ['unused', 'active', 'expired', 'revoked']

// Generate modal
const showGenerateModal = ref(false)
const generating = ref(false)
const generateForm = ref({ router_id: '', hotspot_profile: '', count: 10, duration_hours: 1 })
const hotspotProfiles = ref<HotspotProfile[]>([])
const profilesLoading = ref(false)
const generatedCodes = ref<string[]>([])
const showCodesModal = ref(false)

// Revoke confirm
const confirmRevoke = ref(false)
const revokingId = ref('')
const revoking = ref(false)

// Clipboard feedback
const copiedCode = ref('')

async function loadVouchers() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (filterStatus.value) params.status = filterStatus.value
    const { data } = await getVouchers(params)
    vouchers.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('Failed to load vouchers', e)
  } finally {
    loading.value = false
  }
}

async function loadRouters() {
  try {
    const { data } = await getRouters()
    routers.value = data
  } catch (e) {
    console.error('Failed to load routers', e)
  }
}

async function loadProfiles(routerId: string) {
  if (!routerId) { hotspotProfiles.value = []; return }
  profilesLoading.value = true
  try {
    const { data } = await getHotspotProfiles(routerId)
    hotspotProfiles.value = data
    if (data.length > 0) generateForm.value.hotspot_profile = data[0].name
  } catch (e) {
    console.error('Failed to load hotspot profiles', e)
    hotspotProfiles.value = []
  } finally {
    profilesLoading.value = false
  }
}

function openGenerate() {
  generateForm.value = {
    router_id: routers.value[0]?.id || '',
    hotspot_profile: '',
    count: 10,
    duration_hours: 1,
  }
  hotspotProfiles.value = []
  if (generateForm.value.router_id) loadProfiles(generateForm.value.router_id)
  showGenerateModal.value = true
}

async function doGenerate() {
  generating.value = true
  try {
    const { data } = await generateVouchers({
      router_id: generateForm.value.router_id,
      hotspot_profile: generateForm.value.hotspot_profile,
      count: generateForm.value.count,
      duration_hours: generateForm.value.duration_hours,
    })
    generatedCodes.value = data.map((v: VoucherType) => v.code)
    showGenerateModal.value = false
    showCodesModal.value = true
    await loadVouchers()
  } catch (e) {
    console.error('Failed to generate vouchers', e)
  } finally {
    generating.value = false
  }
}

function askRevoke(id: string) {
  revokingId.value = id
  confirmRevoke.value = true
}

async function doRevoke() {
  revoking.value = true
  try {
    await revokeVoucher(revokingId.value)
    confirmRevoke.value = false
    await loadVouchers()
  } catch (e) {
    console.error('Failed to revoke voucher', e)
  } finally {
    revoking.value = false
  }
}

async function copyCode(code: string) {
  try {
    await navigator.clipboard.writeText(code)
  } catch {
    const el = document.createElement('textarea')
    el.value = code
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  copiedCode.value = code
  setTimeout(() => { copiedCode.value = '' }, 2000)
}

async function copyAllCodes() {
  await navigator.clipboard.writeText(generatedCodes.value.join('\n'))
}

function getRouterName(routerId: string) {
  return routers.value.find(r => r.id === routerId)?.name || routerId
}

function formatDuration(hours: number) {
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  const rem = hours % 24
  return rem ? `${days}d ${rem}h` : `${days}d`
}

function formatDate(d: string | null) {
  if (!d) return '---'
  return new Date(d).toLocaleDateString('en-PH', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

watch(filterStatus, () => loadVouchers())
watch(() => generateForm.value.router_id, (id) => { if (id) loadProfiles(id) })

onMounted(() => {
  loadVouchers()
  loadRouters()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Hotspot Vouchers</h1>
        <p class="text-sm text-gray-500 mt-1">Generate prepaid WiFi voucher codes for hotspot access</p>
      </div>
      <button
        @click="openGenerate"
        class="inline-flex items-center gap-2 px-4 py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors"
      >
        <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
        Generate Batch
      </button>
    </div>

    <!-- Status Filter -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-4">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-sm font-medium text-gray-500 mr-2">Status:</span>
        <button
          @click="filterStatus = ''"
          :class="['px-3 py-1.5 text-sm rounded-lg font-medium transition-colors', !filterStatus ? 'bg-primary text-white' : 'text-gray-600 hover:bg-gray-100']"
        >All</button>
        <button
          v-for="s in STATUSES" :key="s"
          @click="filterStatus = s"
          :class="['px-3 py-1.5 text-sm rounded-lg font-medium transition-colors capitalize', filterStatus === s ? 'bg-primary text-white' : 'text-gray-600 hover:bg-gray-100']"
        >{{ s }}</button>
      </div>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead>
            <tr class="border-b border-gray-100 bg-gray-50/50">
              <th class="px-4 py-3 font-medium text-gray-500">Code</th>
              <th class="px-4 py-3 font-medium text-gray-500">Router</th>
              <th class="px-4 py-3 font-medium text-gray-500">Profile</th>
              <th class="px-4 py-3 font-medium text-gray-500">Duration</th>
              <th class="px-4 py-3 font-medium text-gray-500">Status</th>
              <th class="px-4 py-3 font-medium text-gray-500">Activated</th>
              <th class="px-4 py-3 font-medium text-gray-500">Expires</th>
              <th class="px-4 py-3 font-medium text-gray-500 text-right">Actions</th>
            </tr>
          </thead>
          <tbody v-if="loading">
            <tr><td colspan="8" class="px-4 py-12 text-center text-gray-400">
              <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
              Loading vouchers...
            </td></tr>
          </tbody>
          <tbody v-else-if="vouchers.length === 0">
            <tr><td colspan="8" class="px-4 py-12 text-center text-gray-400">No vouchers found. Click "Generate Batch" to create some.</td></tr>
          </tbody>
          <tbody v-else>
            <tr v-for="v in vouchers" :key="v.id" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
              <td class="px-4 py-3"><code class="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-800">{{ v.code }}</code></td>
              <td class="px-4 py-3 text-gray-700">{{ getRouterName(v.router_id) }}</td>
              <td class="px-4 py-3 text-gray-700">{{ v.hotspot_profile }}</td>
              <td class="px-4 py-3 text-gray-700">{{ formatDuration(v.duration_hours) }}</td>
              <td class="px-4 py-3"><StatusBadge :status="v.status" /></td>
              <td class="px-4 py-3 text-gray-500 text-xs">{{ formatDate(v.activated_at) }}</td>
              <td class="px-4 py-3 text-gray-500 text-xs">{{ formatDate(v.expires_at) }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button @click="copyCode(v.code)" class="text-xs font-medium transition-colors" :class="copiedCode === v.code ? 'text-green-600' : 'text-primary hover:text-primary-hover'">
                    {{ copiedCode === v.code ? 'Copied!' : 'Copy' }}
                  </button>
                  <button v-if="v.status === 'unused'" @click="askRevoke(v.id)" class="text-xs font-medium text-red-600 hover:text-red-700 transition-colors">Revoke</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Generate Modal -->
    <Modal :open="showGenerateModal" title="Generate Hotspot Vouchers" @close="showGenerateModal = false">
      <form @submit.prevent="doGenerate" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">MikroTik Router</label>
          <select
            v-model="generateForm.router_id"
            required
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="" disabled>Select router</option>
            <option v-for="r in routers" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Hotspot Profile</label>
          <div v-if="profilesLoading" class="text-sm text-gray-400 py-2">Loading profiles from router...</div>
          <select
            v-else
            v-model="generateForm.hotspot_profile"
            required
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
          >
            <option value="" disabled>Select profile</option>
            <option v-for="p in hotspotProfiles" :key="p.name" :value="p.name">
              {{ p.name }} {{ p.rate_limit ? `(${p.rate_limit})` : '' }}
            </option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Count</label>
            <input v-model.number="generateForm.count" type="number" min="1" max="500" required
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors tabular-nums" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Duration (hours)</label>
            <input v-model.number="generateForm.duration_hours" type="number" min="1" required
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors tabular-nums" />
          </div>
        </div>
      </form>
      <template #footer>
        <button @click="showGenerateModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
        <button @click="doGenerate" :disabled="generating || !generateForm.router_id || !generateForm.hotspot_profile"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
          {{ generating ? 'Generating...' : 'Generate' }}
        </button>
      </template>
    </Modal>

    <!-- Generated Codes Modal -->
    <Modal :open="showCodesModal" title="Vouchers Generated" size="lg" @close="showCodesModal = false">
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <p class="text-sm text-gray-600">{{ generatedCodes.length }} voucher codes generated. The code is both the username and password for hotspot login.</p>
          <button @click="copyAllCodes" class="text-sm font-medium text-primary hover:text-primary-hover transition-colors">Copy All</button>
        </div>
        <div class="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
            <div v-for="code in generatedCodes" :key="code" class="flex items-center justify-between bg-white rounded-lg border border-gray-200 px-3 py-2">
              <code class="text-sm font-mono text-gray-800">{{ code }}</code>
              <button @click="copyCode(code)" class="ml-2 text-gray-400 hover:text-primary transition-colors">
                <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M8 2a1 1 0 000 2h2a1 1 0 100-2H8z"/><path d="M3 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v6h-4.586l1.293-1.293a1 1 0 00-1.414-1.414l-3 3a1 1 0 000 1.414l3 3a1 1 0 001.414-1.414L10.414 13H15v3a2 2 0 01-2 2H5a2 2 0 01-2-2V5z"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="showCodesModal = false" class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors">Done</button>
      </template>
    </Modal>

    <!-- Confirm Revoke -->
    <ConfirmDialog :open="confirmRevoke" title="Revoke Voucher" message="Are you sure you want to revoke this voucher? This will make it permanently unusable." confirm-text="Revoke" :danger="true" :loading="revoking" @confirm="doRevoke" @cancel="confirmRevoke = false" />
  </div>
</template>
