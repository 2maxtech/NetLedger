<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { getHotspotUsers, getHotspotSessions, getHotspotProfiles, createHotspotProfile, updateHotspotProfile, deleteHotspotProfile } from '../api/network'
import { getRouters, type RouterType } from '../api/routers'
import Modal from '../components/common/Modal.vue'
import ConfirmDialog from '../components/common/ConfirmDialog.vue'

interface HotspotUser {
  '.id': string; name: string; profile: string; password?: string; disabled: string
  'limit-bytes-total'?: string; 'bytes-in'?: string; 'bytes-out'?: string
}
interface HotspotSession {
  '.id': string; user: string; address: string; 'mac-address': string; uptime: string; 'bytes-in': string; 'bytes-out': string
}
interface HotspotProfile {
  '.id': string; name: string; 'rate-limit'?: string; 'session-timeout'?: string; 'shared-users'?: string; 'address-pool'?: string; default?: string
}

const routers = ref<RouterType[]>([])
const selectedRouter = ref('')
const activeTab = ref<'profiles' | 'users' | 'sessions'>('profiles')

const users = ref<HotspotUser[]>([])
const sessions = ref<HotspotSession[]>([])
const profiles = ref<HotspotProfile[]>([])
const loadingUsers = ref(false)
const loadingSessions = ref(false)
const loadingProfiles = ref(false)

// Profile modal
const showProfileModal = ref(false)
const editingProfile = ref<HotspotProfile | null>(null)
const profileSaving = ref(false)
const profileError = ref('')
const profileForm = ref({ name: '', rate_limit: '', session_timeout: '', shared_users: '1', address_pool: '' })

// Delete confirm
const showDeleteConfirm = ref(false)
const deleteTarget = ref<HotspotProfile | null>(null)
const deleting = ref(false)

async function loadRouters() {
  try {
    const { data } = await getRouters()
    routers.value = data.filter((r: RouterType) => r.is_active)
    if (routers.value.length > 0 && !selectedRouter.value) {
      selectedRouter.value = routers.value[0].id
    }
  } catch (e) { console.error('Failed to load routers', e) }
}

async function loadProfiles() {
  if (!selectedRouter.value) return
  loadingProfiles.value = true
  try {
    const { data } = await getHotspotProfiles(selectedRouter.value)
    profiles.value = (data.profiles || []) as HotspotProfile[]
  } catch (e) { console.error('Failed to load profiles', e) }
  finally { loadingProfiles.value = false }
}

async function loadUsers() {
  if (!selectedRouter.value) return
  loadingUsers.value = true
  try {
    const { data } = await getHotspotUsers(selectedRouter.value)
    users.value = (data.users || data) as HotspotUser[]
  } catch (e) { console.error('Failed to load users', e) }
  finally { loadingUsers.value = false }
}

async function loadSessions() {
  if (!selectedRouter.value) return
  loadingSessions.value = true
  try {
    const { data } = await getHotspotSessions(selectedRouter.value)
    sessions.value = (data.sessions || data) as HotspotSession[]
  } catch (e) { console.error('Failed to load sessions', e) }
  finally { loadingSessions.value = false }
}

function loadTabData() {
  if (activeTab.value === 'profiles') loadProfiles()
  else if (activeTab.value === 'users') loadUsers()
  else loadSessions()
}

function openAddProfile() {
  editingProfile.value = null
  profileForm.value = { name: '', rate_limit: '', session_timeout: '', shared_users: '1', address_pool: '' }
  profileError.value = ''
  showProfileModal.value = true
}

function openEditProfile(p: HotspotProfile) {
  editingProfile.value = p
  profileForm.value = {
    name: p.name,
    rate_limit: p['rate-limit'] || '',
    session_timeout: p['session-timeout'] || '',
    shared_users: p['shared-users'] || '1',
    address_pool: p['address-pool'] || '',
  }
  profileError.value = ''
  showProfileModal.value = true
}

async function saveProfile() {
  if (!profileForm.value.name) { profileError.value = 'Profile name is required'; return }
  profileSaving.value = true
  profileError.value = ''
  try {
    if (editingProfile.value) {
      await updateHotspotProfile(editingProfile.value['.id'], { router_id: selectedRouter.value, ...profileForm.value })
    } else {
      await createHotspotProfile({ router_id: selectedRouter.value, ...profileForm.value })
    }
    showProfileModal.value = false
    await loadProfiles()
  } catch (e: any) {
    profileError.value = e.response?.data?.detail || 'Failed to save profile'
  } finally { profileSaving.value = false }
}

function confirmDeleteProfile(p: HotspotProfile) {
  deleteTarget.value = p
  showDeleteConfirm.value = true
}

async function doDeleteProfile() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteHotspotProfile(deleteTarget.value['.id'], selectedRouter.value)
    showDeleteConfirm.value = false
    deleteTarget.value = null
    await loadProfiles()
  } catch (e: any) {
    console.error('Failed to delete profile', e)
  } finally { deleting.value = false }
}

function formatBytes(bytes: string | undefined): string {
  if (!bytes) return '---'
  const b = parseInt(bytes, 10)
  if (isNaN(b) || b === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(b) / Math.log(1024))
  return (b / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

watch(selectedRouter, () => loadTabData())
watch(activeTab, () => loadTabData())
onMounted(async () => { await loadRouters() })
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Hotspot Management</h1>
        <p class="text-sm text-gray-500 mt-1">Manage hotspot profiles, users, and active sessions</p>
      </div>
      <div class="flex items-center gap-3">
        <label class="text-sm font-medium text-gray-500">Router:</label>
        <select
          v-model="selectedRouter"
          class="rounded-lg border border-gray-300 text-sm px-3 py-2.5 min-w-[200px] focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
        >
          <option value="" disabled>Select a router</option>
          <option v-for="r in routers" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
      </div>
    </div>

    <!-- Tabs -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="border-b border-gray-100">
        <div class="flex">
          <button
            v-for="tab in ([
              { key: 'profiles', label: 'Profiles', count: profiles.length },
              { key: 'users', label: 'Users', count: users.length },
              { key: 'sessions', label: 'Active Sessions', count: sessions.length },
            ] as const)" :key="tab.key"
            @click="activeTab = tab.key"
            :class="['px-6 py-3 text-sm font-medium border-b-2 transition-colors', activeTab === tab.key ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700']"
          >
            <div class="flex items-center gap-2">
              {{ tab.label }}
              <span class="bg-gray-100 text-gray-600 text-xs font-semibold rounded-full px-2 py-0.5 tabular-nums">{{ tab.count }}</span>
            </div>
          </button>
        </div>
      </div>

      <!-- Profiles Tab -->
      <div v-if="activeTab === 'profiles'">
        <div class="px-4 py-3 border-b border-gray-100 flex justify-end">
          <button @click="openAddProfile" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors">
            <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
            Add Profile
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm text-left">
            <thead>
              <tr class="border-b border-gray-100 bg-gray-50/50">
                <th class="px-4 py-3 font-medium text-gray-500">Name</th>
                <th class="px-4 py-3 font-medium text-gray-500">Rate Limit</th>
                <th class="px-4 py-3 font-medium text-gray-500">Session Timeout</th>
                <th class="px-4 py-3 font-medium text-gray-500">Shared Users</th>
                <th class="px-4 py-3 font-medium text-gray-500 text-right">Actions</th>
              </tr>
            </thead>
            <tbody v-if="loadingProfiles">
              <tr><td colspan="5" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                Loading profiles...
              </td></tr>
            </tbody>
            <tbody v-else-if="profiles.length === 0">
              <tr><td colspan="5" class="px-4 py-12 text-center text-gray-400">No hotspot profiles found on this router.</td></tr>
            </tbody>
            <tbody v-else>
              <tr v-for="p in profiles" :key="p['.id']" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="px-4 py-3 font-medium text-gray-900">
                  {{ p.name }}
                  <span v-if="p.default === 'true'" class="ml-2 text-[10px] font-medium text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">DEFAULT</span>
                </td>
                <td class="px-4 py-3 text-gray-700 font-mono text-xs">{{ p['rate-limit'] || 'none' }}</td>
                <td class="px-4 py-3 text-gray-700">{{ p['session-timeout'] || 'none' }}</td>
                <td class="px-4 py-3 text-gray-700">{{ p['shared-users'] || '1' }}</td>
                <td class="px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-2">
                    <button @click="openEditProfile(p)" class="text-xs font-medium text-primary hover:text-primary-hover transition-colors">Edit</button>
                    <button v-if="p.default !== 'true'" @click="confirmDeleteProfile(p)" class="text-xs font-medium text-red-600 hover:text-red-700 transition-colors">Delete</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Users Tab -->
      <div v-if="activeTab === 'users'">
        <div class="overflow-x-auto">
          <table class="w-full text-sm text-left">
            <thead>
              <tr class="border-b border-gray-100 bg-gray-50/50">
                <th class="px-4 py-3 font-medium text-gray-500">Name</th>
                <th class="px-4 py-3 font-medium text-gray-500">Profile</th>
                <th class="px-4 py-3 font-medium text-gray-500">Password</th>
                <th class="px-4 py-3 font-medium text-gray-500">Status</th>
                <th class="px-4 py-3 font-medium text-gray-500">Bytes In</th>
                <th class="px-4 py-3 font-medium text-gray-500">Bytes Out</th>
              </tr>
            </thead>
            <tbody v-if="loadingUsers">
              <tr><td colspan="6" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                Loading users...
              </td></tr>
            </tbody>
            <tbody v-else-if="users.length === 0">
              <tr><td colspan="6" class="px-4 py-12 text-center text-gray-400">No hotspot users found.</td></tr>
            </tbody>
            <tbody v-else>
              <tr v-for="u in users" :key="u['.id']" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="px-4 py-3 font-medium text-gray-900">{{ u.name }}</td>
                <td class="px-4 py-3 text-gray-700">{{ u.profile }}</td>
                <td class="px-4 py-3"><code class="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600">{{ u.password || '***' }}</code></td>
                <td class="px-4 py-3">
                  <span :class="['inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium', u.disabled === 'true' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700']">
                    <span :class="['w-1.5 h-1.5 rounded-full', u.disabled === 'true' ? 'bg-red-500' : 'bg-green-500']" />
                    {{ u.disabled === 'true' ? 'Disabled' : 'Enabled' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-gray-500 tabular-nums">{{ formatBytes(u['bytes-in']) }}</td>
                <td class="px-4 py-3 text-gray-500 tabular-nums">{{ formatBytes(u['bytes-out']) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-3 border-t border-gray-100 text-sm text-gray-500">{{ users.length }} user{{ users.length !== 1 ? 's' : '' }}</div>
      </div>

      <!-- Sessions Tab -->
      <div v-if="activeTab === 'sessions'">
        <div class="overflow-x-auto">
          <table class="w-full text-sm text-left">
            <thead>
              <tr class="border-b border-gray-100 bg-gray-50/50">
                <th class="px-4 py-3 font-medium text-gray-500">User</th>
                <th class="px-4 py-3 font-medium text-gray-500">IP Address</th>
                <th class="px-4 py-3 font-medium text-gray-500">MAC Address</th>
                <th class="px-4 py-3 font-medium text-gray-500">Uptime</th>
                <th class="px-4 py-3 font-medium text-gray-500">Bytes In</th>
                <th class="px-4 py-3 font-medium text-gray-500">Bytes Out</th>
              </tr>
            </thead>
            <tbody v-if="loadingSessions">
              <tr><td colspan="6" class="px-4 py-12 text-center text-gray-400">
                <svg class="w-6 h-6 animate-spin mx-auto mb-2 text-primary" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                Loading sessions...
              </td></tr>
            </tbody>
            <tbody v-else-if="sessions.length === 0">
              <tr><td colspan="6" class="px-4 py-12 text-center text-gray-400">No active hotspot sessions.</td></tr>
            </tbody>
            <tbody v-else>
              <tr v-for="s in sessions" :key="s['.id']" class="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
                <td class="px-4 py-3 font-medium text-gray-900">{{ s.user }}</td>
                <td class="px-4 py-3"><code class="text-sm font-mono text-gray-700">{{ s.address }}</code></td>
                <td class="px-4 py-3"><code class="text-sm font-mono text-gray-500">{{ s['mac-address'] }}</code></td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-1 text-gray-700">
                    <svg class="w-3.5 h-3.5 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg>
                    {{ s.uptime }}
                  </span>
                </td>
                <td class="px-4 py-3 text-gray-500 tabular-nums">{{ formatBytes(s['bytes-in']) }}</td>
                <td class="px-4 py-3 text-gray-500 tabular-nums">{{ formatBytes(s['bytes-out']) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="px-4 py-3 border-t border-gray-100 text-sm text-gray-500">{{ sessions.length }} active session{{ sessions.length !== 1 ? 's' : '' }}</div>
      </div>
    </div>

    <!-- Profile Add/Edit Modal -->
    <Modal :open="showProfileModal" :title="editingProfile ? 'Edit Profile' : 'Add Hotspot Profile'" @close="showProfileModal = false">
      <form @submit.prevent="saveProfile" class="space-y-4">
        <div v-if="profileError" class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{{ profileError }}</div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Profile Name *</label>
          <input v-model="profileForm.name" type="text" required placeholder="e.g. 1hr-5M"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Rate Limit</label>
          <input v-model="profileForm.rate_limit" type="text" placeholder="e.g. 5M/10M (upload/download)"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
          <p class="text-xs text-gray-400 mt-1">Format: upload/download (e.g. 5M/10M)</p>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Session Timeout</label>
            <input v-model="profileForm.session_timeout" type="text" placeholder="e.g. 1h, 1d, 30m"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">Shared Users</label>
            <input v-model="profileForm.shared_users" type="number" min="1" placeholder="1"
              class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Address Pool</label>
          <input v-model="profileForm.address_pool" type="text" placeholder="e.g. hotspot-pool"
            class="w-full rounded-lg border border-gray-300 text-sm px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
      </form>
      <template #footer>
        <button @click="showProfileModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
        <button @click="saveProfile" :disabled="profileSaving || !profileForm.name"
          class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
          {{ profileSaving ? 'Saving...' : editingProfile ? 'Update' : 'Create' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm -->
    <ConfirmDialog :open="showDeleteConfirm" title="Delete Profile" :message="`Delete hotspot profile '${deleteTarget?.name}'? Users assigned to this profile will lose access.`"
      confirm-text="Delete" :danger="true" :loading="deleting" @confirm="doDeleteProfile" @cancel="showDeleteConfirm = false" />
  </div>
</template>
