<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import StatusBadge from '../components/common/StatusBadge.vue'
import { getTicket, updateTicket, addTicketMessage } from '../api/tickets'
import type { TicketType, TicketMessage } from '../api/tickets'
import { getUsers } from '../api/users'

const route = useRoute()
const ticketId = route.params.id as string

const ticket = ref<TicketType | null>(null)
const loading = ref(false)
const updating = ref(false)
const sending = ref(false)

const messagesContainer = ref<HTMLElement | null>(null)
const newMessage = ref('')
const staffUsers = ref<Array<{ id: string; full_name: string | null; username: string }>>([])

const updateForm = ref({
  status: '',
  priority: '',
  assigned_to: '',
})

const statusOptions = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

const priorityOptions = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

async function loadTicket() {
  loading.value = true
  try {
    const res = await getTicket(ticketId)
    ticket.value = res.data
    updateForm.value = {
      status: res.data.status,
      priority: res.data.priority,
      assigned_to: res.data.assigned_to || '',
    }
    await nextTick()
    scrollToBottom()
  } catch (e) {
    console.error('Failed to load ticket:', e)
  } finally {
    loading.value = false
  }
}

async function handleUpdate() {
  updating.value = true
  try {
    const payload: Record<string, string | null> = {}
    if (updateForm.value.status !== ticket.value?.status) payload.status = updateForm.value.status
    if (updateForm.value.priority !== ticket.value?.priority) payload.priority = updateForm.value.priority
    if (updateForm.value.assigned_to !== (ticket.value?.assigned_to || ''))
      payload.assigned_to = updateForm.value.assigned_to || null
    if (Object.keys(payload).length) {
      await updateTicket(ticketId, payload)
      await loadTicket()
    }
  } catch (e) {
    console.error('Failed to update ticket:', e)
  } finally {
    updating.value = false
  }
}

async function handleSendMessage() {
  if (!newMessage.value.trim()) return
  sending.value = true
  try {
    await addTicketMessage(ticketId, {
      message: newMessage.value.trim(),
      sender_type: 'staff',
    })
    newMessage.value = ''
    await loadTicket()
  } catch (e) {
    console.error('Failed to send message:', e)
  } finally {
    sending.value = false
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function loadStaff() {
  try {
    const { data } = await getUsers()
    staffUsers.value = data
  } catch { /* ignore */ }
}

onMounted(() => {
  loadTicket()
  loadStaff()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <router-link
        to="/tickets"
        class="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clip-rule="evenodd" />
        </svg>
        Back
      </router-link>
      <div v-if="ticket" class="flex items-center gap-3">
        <h1 class="text-2xl font-bold text-gray-900">{{ ticket.subject }}</h1>
        <StatusBadge :status="ticket.status" />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <div class="space-y-3">
          <div class="h-4 bg-gray-100 rounded animate-pulse w-1/3" />
          <div class="h-4 bg-gray-100 rounded animate-pulse w-1/2" />
          <div class="h-4 bg-gray-100 rounded animate-pulse w-1/4" />
        </div>
      </div>
    </div>

    <template v-else-if="ticket">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left: Messages -->
        <div class="lg:col-span-2 space-y-4">
          <!-- Message Thread -->
          <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100">
              <h2 class="text-sm font-semibold text-gray-800">Messages</h2>
            </div>
            <div ref="messagesContainer" class="p-4 space-y-4 max-h-[500px] overflow-y-auto">
              <div v-if="!ticket.messages?.length" class="py-8 text-center text-gray-400 text-sm">
                No messages yet
              </div>
              <div
                v-for="msg in ticket.messages"
                :key="msg.id"
                :class="[
                  'flex',
                  msg.sender_type === 'staff' ? 'justify-end' : 'justify-start'
                ]"
              >
                <div
                  :class="[
                    'max-w-[75%] rounded-xl px-4 py-3',
                    msg.sender_type === 'staff'
                      ? 'bg-primary text-white'
                      : 'bg-gray-100 text-gray-800'
                  ]"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <span
                      :class="[
                        'inline-flex px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase',
                        msg.sender_type === 'staff'
                          ? 'bg-white/20 text-white'
                          : 'bg-gray-200 text-gray-600'
                      ]"
                    >
                      {{ msg.sender_name || msg.sender_type }}
                    </span>
                    <span
                      :class="[
                        'text-[11px]',
                        msg.sender_type === 'staff' ? 'text-white/70' : 'text-gray-400'
                      ]"
                    >
                      {{ dayjs(msg.created_at).format('MMM D, h:mm A') }}
                    </span>
                  </div>
                  <p class="text-sm whitespace-pre-wrap">{{ msg.message }}</p>
                </div>
              </div>
            </div>

            <!-- Send Message -->
            <div class="border-t border-gray-100 p-4">
              <form @submit.prevent="handleSendMessage" class="flex gap-3">
                <textarea
                  v-model="newMessage"
                  rows="2"
                  placeholder="Type your reply..."
                  class="flex-1 px-3 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
                  @keydown.ctrl.enter="handleSendMessage"
                />
                <button
                  type="submit"
                  :disabled="sending || !newMessage.trim()"
                  class="self-end inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary-hover transition-colors disabled:opacity-50"
                >
                  <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
                  </svg>
                  {{ sending ? 'Sending...' : 'Send' }}
                </button>
              </form>
            </div>
          </div>
        </div>

        <!-- Right: Info + Controls -->
        <div class="space-y-4">
          <!-- Ticket Info -->
          <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
            <h2 class="text-sm font-semibold text-gray-800 mb-4">Ticket Details</h2>
            <dl class="space-y-3">
              <div class="flex justify-between">
                <dt class="text-sm text-gray-500">Customer</dt>
                <dd class="text-sm font-medium text-gray-900">{{ ticket.customer_name || ticket.customer_id.substring(0, 8) }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-sm text-gray-500">Status</dt>
                <dd><StatusBadge :status="ticket.status" /></dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-sm text-gray-500">Priority</dt>
                <dd><StatusBadge :status="ticket.priority" /></dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-sm text-gray-500">Assigned To</dt>
                <dd class="text-sm font-medium text-gray-900">{{ ticket.assigned_to_name || 'Unassigned' }}</dd>
              </div>
              <div class="flex justify-between">
                <dt class="text-sm text-gray-500">Created</dt>
                <dd class="text-sm text-gray-700">{{ dayjs(ticket.created_at).format('MMM D, YYYY h:mm A') }}</dd>
              </div>
              <div v-if="ticket.resolved_at" class="flex justify-between">
                <dt class="text-sm text-gray-500">Resolved</dt>
                <dd class="text-sm text-gray-700">{{ dayjs(ticket.resolved_at).format('MMM D, YYYY h:mm A') }}</dd>
              </div>
            </dl>
          </div>

          <!-- Update Controls -->
          <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
            <h2 class="text-sm font-semibold text-gray-800 mb-4">Update Ticket</h2>
            <form @submit.prevent="handleUpdate" class="space-y-3">
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Status</label>
                <select
                  v-model="updateForm.status"
                  class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                >
                  <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Priority</label>
                <select
                  v-model="updateForm.priority"
                  class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                >
                  <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Assigned To</label>
                <select
                  v-model="updateForm.assigned_to"
                  class="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
                >
                  <option value="">Unassigned</option>
                  <option v-for="s in staffUsers" :key="s.id" :value="s.id">{{ s.full_name || s.username }}</option>
                </select>
              </div>
              <button
                type="submit"
                :disabled="updating"
                class="w-full px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
              >
                {{ updating ? 'Updating...' : 'Update' }}
              </button>
            </form>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
