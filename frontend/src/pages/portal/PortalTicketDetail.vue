<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { getPortalTicket, addPortalTicketMessage } from '../../api/portal'
import StatusBadge from '../../components/common/StatusBadge.vue'

const route = useRoute()
const slug = route.params.slug as string
const ticketId = route.params.id as string

const ticket = ref<any>(null)
const messages = ref<any[]>([])
const loading = ref(true)

const newMessage = ref('')
const sending = ref(false)

const messagesContainer = ref<HTMLElement | null>(null)

// Get the current customer from localStorage
const portalCustomer = (() => {
  const raw = localStorage.getItem('portal_customer')
  return raw ? JSON.parse(raw) : null
})()

async function fetchTicket() {
  loading.value = true
  try {
    const { data } = await getPortalTicket(ticketId)
    ticket.value = data.ticket || data
    messages.value = data.messages || data.ticket?.messages || []
  } catch (e) {
    console.error('Failed to load ticket', e)
  } finally {
    loading.value = false
  }
}

async function handleSend() {
  if (!newMessage.value.trim()) return
  sending.value = true
  try {
    await addPortalTicketMessage(ticketId, { message: newMessage.value })
    newMessage.value = ''
    await fetchTicket()
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  } catch (e) {
    console.error('Failed to send message', e)
  } finally {
    sending.value = false
  }
}

function isCustomerMessage(msg: any) {
  return msg.sender_type === 'customer' || msg.customer_id === portalCustomer?.id
}

onMounted(fetchTicket)
</script>

<template>
  <div class="space-y-6">
    <!-- Back link -->
    <router-link
      :to="`/portal/${slug}/tickets`"
      class="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary transition-colors"
    >
      <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clip-rule="evenodd" />
      </svg>
      Back to Tickets
    </router-link>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <div class="h-6 w-64 bg-gray-100 rounded animate-pulse mb-3" />
        <div class="h-4 w-40 bg-gray-100 rounded animate-pulse" />
      </div>
    </div>

    <template v-else-if="ticket">
      <!-- Ticket Info -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 p-6">
        <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 class="text-xl font-bold text-gray-900">{{ ticket.subject }}</h1>
            <div class="flex items-center gap-3 mt-2">
              <StatusBadge :status="ticket.status" />
              <StatusBadge :status="ticket.priority" />
              <span class="text-sm text-gray-500">
                Created {{ dayjs(ticket.created_at).format('MMM D, YYYY h:mm A') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <div class="rounded-xl bg-white shadow-sm border border-gray-100 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-100">
          <h2 class="text-sm font-semibold text-gray-800">Messages</h2>
        </div>
        <div
          ref="messagesContainer"
          class="p-6 space-y-4 max-h-[500px] overflow-y-auto"
        >
          <div v-if="!messages.length" class="text-center py-8 text-gray-400 text-sm">
            No messages yet
          </div>
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="[
              'flex',
              isCustomerMessage(msg) ? 'justify-end' : 'justify-start'
            ]"
          >
            <div :class="[
              'max-w-[75%] rounded-xl px-4 py-3',
              isCustomerMessage(msg)
                ? 'bg-primary/10 text-gray-800'
                : 'bg-gray-100 text-gray-800'
            ]">
              <div class="flex items-center gap-2 mb-1">
                <span class="text-xs font-semibold" :class="isCustomerMessage(msg) ? 'text-primary' : 'text-gray-600'">
                  {{ isCustomerMessage(msg) ? 'You' : (msg.sender_name || 'Support') }}
                </span>
                <span class="text-xs text-gray-400">
                  {{ dayjs(msg.created_at).format('MMM D, h:mm A') }}
                </span>
              </div>
              <p class="text-sm whitespace-pre-wrap">{{ msg.message || msg.content }}</p>
            </div>
          </div>
        </div>

        <!-- Send Message -->
        <div class="px-6 py-4 border-t border-gray-100 bg-gray-50">
          <form @submit.prevent="handleSend" class="flex gap-3">
            <textarea
              v-model="newMessage"
              rows="2"
              placeholder="Type your message..."
              class="flex-1 px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors resize-none"
            />
            <button
              type="submit"
              :disabled="sending || !newMessage.trim()"
              class="self-end px-4 py-2 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
            >
              {{ sending ? 'Sending...' : 'Send' }}
            </button>
          </form>
        </div>
      </div>
    </template>

    <!-- Not Found -->
    <div v-else class="rounded-xl bg-white shadow-sm border border-gray-100 p-12 text-center">
      <p class="text-gray-500">Ticket not found</p>
    </div>
  </div>
</template>
