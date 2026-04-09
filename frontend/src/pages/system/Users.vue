<script setup lang="ts">
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { getUsers, getPermissionModules, createUser, updateUser, deleteUser, type StaffUser, type PermissionModule } from '../../api/users'
import { useAuth } from '../../composables/useAuth'
import Modal from '../../components/common/Modal.vue'
import ConfirmDialog from '../../components/common/ConfirmDialog.vue'

const { user: currentUser } = useAuth()

const users = ref<StaffUser[]>([])
const permModules = ref<PermissionModule[]>([])
const loading = ref(false)

// Add modal
const showAddModal = ref(false)
const addForm = ref({ username: '', email: '', password: '', role: 'staff', permissions: [] as string[] })
const addLoading = ref(false)
const addError = ref('')

// Edit modal
const showEditModal = ref(false)
const editForm = ref({ id: '', username: '', email: '', password: '', role: '', permissions: [] as string[], is_active: true })
const editLoading = ref(false)
const editError = ref('')

// Delete confirm
const showDeleteConfirm = ref(false)
const deleteTarget = ref<StaffUser | null>(null)
const deleteLoading = ref(false)

const roleColors: Record<string, { bg: string; text: string }> = {
  admin: { bg: 'bg-orange-50', text: 'text-orange-700' },
  staff: { bg: 'bg-blue-50', text: 'text-blue-700' },
  billing: { bg: 'bg-amber-50', text: 'text-amber-700' },
  technician: { bg: 'bg-gray-100', text: 'text-gray-700' },
}

function displayRole(role: string) {
  if (role === 'admin') return 'Admin'
  return 'Staff'
}

function isStaffRole(role: string) {
  return role === 'staff' || role === 'billing' || role === 'technician'
}

async function fetchUsers() {
  loading.value = true
  try {
    const { data } = await getUsers()
    users.value = data
  } catch (e) {
    console.error('Failed to fetch users', e)
  } finally {
    loading.value = false
  }
}

async function fetchPermissions() {
  try {
    const { data } = await getPermissionModules()
    permModules.value = data
  } catch { /* ignore */ }
}

function openAddModal() {
  addForm.value = { username: '', email: '', password: '', role: 'staff', permissions: [] }
  addError.value = ''
  showAddModal.value = true
}

async function handleAdd() {
  addLoading.value = true
  addError.value = ''
  try {
    await createUser({
      ...addForm.value,
      permissions: addForm.value.role === 'staff' ? addForm.value.permissions : [],
    })
    showAddModal.value = false
    fetchUsers()
  } catch (e: any) {
    addError.value = e.response?.data?.detail || 'Failed to create user'
  } finally {
    addLoading.value = false
  }
}

function openEditModal(u: StaffUser) {
  editForm.value = {
    id: u.id,
    username: u.username,
    email: u.email,
    password: '',
    role: isStaffRole(u.role) ? 'staff' : u.role,
    permissions: [...(u.permissions || [])],
    is_active: u.is_active,
  }
  editError.value = ''
  showEditModal.value = true
}

async function handleEdit() {
  editLoading.value = true
  editError.value = ''
  try {
    const payload: Record<string, any> = {
      username: editForm.value.username,
      email: editForm.value.email,
      role: editForm.value.role,
      permissions: editForm.value.role === 'staff' ? editForm.value.permissions : [],
      is_active: editForm.value.is_active,
    }
    if (editForm.value.password) {
      payload.password = editForm.value.password
    }
    await updateUser(editForm.value.id, payload)
    showEditModal.value = false
    fetchUsers()
  } catch (e: any) {
    editError.value = e.response?.data?.detail || 'Failed to update user'
  } finally {
    editLoading.value = false
  }
}

function openDeleteConfirm(u: StaffUser) {
  deleteTarget.value = u
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  try {
    await deleteUser(deleteTarget.value.id)
    showDeleteConfirm.value = false
    deleteTarget.value = null
    fetchUsers()
  } catch (e: any) {
    console.error('Delete failed', e)
  } finally {
    deleteLoading.value = false
  }
}

function canDelete(u: StaffUser) {
  return currentUser.value?.id !== u.id
}

function togglePerm(perms: string[], key: string) {
  const idx = perms.indexOf(key)
  if (idx >= 0) perms.splice(idx, 1)
  else perms.push(key)
}

onMounted(() => {
  fetchUsers()
  fetchPermissions()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <h1 class="text-2xl font-bold text-gray-900">Staff Users</h1>
      <button
        @click="openAddModal"
        class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors"
      >
        Add User
      </button>
    </div>

    <!-- Table -->
    <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Username</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Email</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Role</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Permissions</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Status</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-left">Created</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <template v-if="loading">
              <tr v-for="i in 3" :key="i">
                <td v-for="j in 7" :key="j" class="px-4 py-3">
                  <div class="h-4 bg-gray-100 rounded animate-pulse" />
                </td>
              </tr>
            </template>
            <tr v-else-if="!users.length">
              <td colspan="7" class="px-4 py-12 text-center text-gray-400">No staff users yet</td>
            </tr>
            <tr v-else v-for="u in users" :key="u.id" class="hover:bg-gray-50/50 transition-colors">
              <td class="px-4 py-3 text-sm text-gray-700 font-medium">{{ u.username }}</td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ u.email }}</td>
              <td class="px-4 py-3">
                <span :class="[
                  'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                  roleColors[u.role]?.bg || roleColors.staff.bg,
                  roleColors[u.role]?.text || roleColors.staff.text
                ]">
                  {{ displayRole(u.role) }}
                </span>
              </td>
              <td class="px-4 py-3">
                <template v-if="u.role === 'admin'">
                  <span class="text-xs text-gray-400">Full access</span>
                </template>
                <template v-else>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="p in (u.permissions || [])"
                      :key="p"
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700"
                    >{{ p }}</span>
                    <span v-if="!(u.permissions || []).length" class="text-xs text-gray-400">None</span>
                  </div>
                </template>
              </td>
              <td class="px-4 py-3">
                <span :class="[
                  'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium',
                  u.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                ]">
                  <span :class="['w-1.5 h-1.5 rounded-full', u.is_active ? 'bg-green-500' : 'bg-gray-400']" />
                  {{ u.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-gray-500">{{ dayjs(u.created_at).format('MMM D, YYYY') }}</td>
              <td class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <button
                    @click="openEditModal(u)"
                    title="Edit user"
                    class="p-1.5 rounded-lg text-gray-400 hover:text-primary hover:bg-orange-50 transition-colors"
                  >
                    <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg>
                  </button>
                  <button
                    v-if="canDelete(u)"
                    @click="openDeleteConfirm(u)"
                    title="Delete user"
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
    </div>

    <!-- Add User Modal -->
    <Modal :open="showAddModal" title="Add User" @close="showAddModal = false">
      <div v-if="addError" class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{{ addError }}</div>
      <form @submit.prevent="handleAdd" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
          <input v-model="addForm.username" type="text" required class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
          <input v-model="addForm.email" type="email" required class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
          <input v-model="addForm.password" type="password" required class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Role</label>
          <select v-model="addForm.role" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors">
            <option value="admin">Admin (full access)</option>
            <option value="staff">Staff (custom permissions)</option>
          </select>
        </div>
        <!-- Permissions grid (only for staff) -->
        <div v-if="addForm.role === 'staff'" class="space-y-2">
          <label class="block text-sm font-medium text-gray-700">Permissions</label>
          <div class="grid grid-cols-2 gap-2">
            <label
              v-for="mod in permModules"
              :key="mod.key"
              class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors cursor-pointer"
              :class="addForm.permissions.includes(mod.key) ? 'border-primary bg-primary/5' : 'border-gray-200 hover:border-gray-300'"
            >
              <input
                type="checkbox"
                :checked="addForm.permissions.includes(mod.key)"
                @change="togglePerm(addForm.permissions, mod.key)"
                class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary/30"
              />
              <span class="text-sm text-gray-700">{{ mod.label }}</span>
            </label>
          </div>
          <p v-if="!addForm.permissions.length" class="text-xs text-amber-600">Select at least one permission for this user.</p>
        </div>
      </form>
      <template #footer>
        <button @click="showAddModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
        <button @click="handleAdd" :disabled="addLoading" class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
          {{ addLoading ? 'Creating...' : 'Create User' }}
        </button>
      </template>
    </Modal>

    <!-- Edit User Modal -->
    <Modal :open="showEditModal" title="Edit User" @close="showEditModal = false">
      <div v-if="editError" class="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{{ editError }}</div>
      <form @submit.prevent="handleEdit" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Username</label>
          <input v-model="editForm.username" type="text" required class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
          <input v-model="editForm.email" type="email" required class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Password <span class="text-gray-400 font-normal">(leave blank to keep current)</span></label>
          <input v-model="editForm.password" type="password" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1.5">Role</label>
          <select v-model="editForm.role" class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors">
            <option value="admin">Admin (full access)</option>
            <option value="staff">Staff (custom permissions)</option>
          </select>
        </div>
        <!-- Permissions grid (only for staff) -->
        <div v-if="editForm.role === 'staff'" class="space-y-2">
          <label class="block text-sm font-medium text-gray-700">Permissions</label>
          <div class="grid grid-cols-2 gap-2">
            <label
              v-for="mod in permModules"
              :key="mod.key"
              class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors cursor-pointer"
              :class="editForm.permissions.includes(mod.key) ? 'border-primary bg-primary/5' : 'border-gray-200 hover:border-gray-300'"
            >
              <input
                type="checkbox"
                :checked="editForm.permissions.includes(mod.key)"
                @change="togglePerm(editForm.permissions, mod.key)"
                class="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary/30"
              />
              <span class="text-sm text-gray-700">{{ mod.label }}</span>
            </label>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <label class="relative inline-flex items-center cursor-pointer">
            <input v-model="editForm.is_active" type="checkbox" class="sr-only peer" />
            <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary/30 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
          </label>
          <span class="text-sm font-medium text-gray-700">Active</span>
        </div>
      </form>
      <template #footer>
        <button @click="showEditModal = false" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">Cancel</button>
        <button @click="handleEdit" :disabled="editLoading" class="px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50">
          {{ editLoading ? 'Saving...' : 'Save Changes' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="Delete User"
      :message="`Are you sure you want to delete '${deleteTarget?.username}'? This action cannot be undone.`"
      confirm-text="Delete"
      :danger="true"
      :loading="deleteLoading"
      @confirm="handleDelete"
      @cancel="showDeleteConfirm = false; deleteTarget = null"
    />
  </div>
</template>
