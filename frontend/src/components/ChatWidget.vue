<script setup lang="ts">
import { ref, nextTick, onMounted, watch, computed } from 'vue'

const props = defineProps<{
  mode: 'public' | 'tenant'
}>()

// ── State ────────────────────────────────────────────────────────────
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface AttachedImage {
  id: string
  url: string
  name: string
}

const chatAvailable = ref(true)
const isOpen = ref(false)
const currentMessage = ref('')
const messages = ref<ChatMessage[]>([])
const attachedImages = ref<AttachedImage[]>([])
const isTyping = ref(false)
const isSending = ref(false)
const errorMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let nextId = 1

// ── Availability check ──────────────────────────────────────────────
onMounted(async () => {
  try {
    const resp = await fetch('/api/v1/chat/status')
    if (!resp.ok) { chatAvailable.value = false; return }
    const data = await resp.json()
    if (!data.available) chatAvailable.value = false
  } catch {
    chatAvailable.value = false
  }
})

// ── Auto-scroll ─────────────────────────────────────────────────────
function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(messages, scrollToBottom, { deep: true })
watch(isTyping, scrollToBottom)

// ── Message trimming (max 50) ───────────────────────────────────────
function trimMessages() {
  if (messages.value.length > 50) {
    messages.value = messages.value.slice(messages.value.length - 50)
  }
}

// ── Send message ────────────────────────────────────────────────────
async function sendMessage() {
  const text = currentMessage.value.trim()
  if (!text && attachedImages.value.length === 0) return
  if (isSending.value) return

  errorMessage.value = ''
  isSending.value = true

  // Add user message
  messages.value.push({ id: nextId++, role: 'user', content: text })
  const imageIds = attachedImages.value.map(img => img.id)
  currentMessage.value = ''
  attachedImages.value = []
  trimMessages()

  // Show typing indicator
  isTyping.value = true

  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = localStorage.getItem('access_token')
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: text,
        history: messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        images: imageIds.length > 0 ? imageIds : undefined,
      }),
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => null)
      throw new Error(errData?.detail || `Request failed (${response.status})`)
    }

    const data = await response.json()
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: data.reply || data.message || 'Sorry, I could not process that request.',
    })
    trimMessages()
  } catch (err: any) {
    errorMessage.value = err.message || 'Something went wrong. Please try again.'
    // Add error as assistant message so user sees it inline
    messages.value.push({
      id: nextId++,
      role: 'assistant',
      content: 'Sorry, something went wrong. Please try again.',
    })
    trimMessages()
  } finally {
    isTyping.value = false
    isSending.value = false
  }
}

// ── Image upload (tenant mode only) ─────────────────────────────────
const canUploadImages = computed(() => props.mode === 'tenant')

function triggerImageUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (!files) return
  for (const file of Array.from(files)) {
    if (!file.type.startsWith('image/')) continue
    await uploadImage(file)
  }
  // Reset so the same file can be re-selected
  target.value = ''
}

async function uploadImage(file: File) {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('access_token')
    const response = await fetch('/api/v1/chat/upload', {
      method: 'POST',
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      body: formData,
    })
    if (!response.ok) throw new Error('Upload failed')
    const data = await response.json()
    attachedImages.value.push({ id: data.id, url: data.url, name: file.name })
  } catch {
    errorMessage.value = 'Failed to upload image. Please try again.'
  }
}

function removeImage(index: number) {
  attachedImages.value.splice(index, 1)
}

// ── Keyboard handling ───────────────────────────────────────────────
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

// ── Toggle panel ────────────────────────────────────────────────────
function toggleChat() {
  isOpen.value = !isOpen.value
}

function closeChat() {
  isOpen.value = false
}
</script>

<template>
  <div v-if="chatAvailable">
    <!-- Floating Button -->
    <button
      @click="toggleChat"
      class="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary text-white shadow-lg shadow-primary/30 hover:scale-110 hover:shadow-xl hover:shadow-primary/40 transition-all duration-200 flex items-center justify-center"
      aria-label="Open chat"
    >
      <!-- Chat bubble icon when closed, X icon when open -->
      <svg v-if="!isOpen" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      <svg v-else class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>

    <!-- Chat Panel -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="translate-y-4 opacity-0 scale-95"
      enter-to-class="translate-y-0 opacity-100 scale-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="translate-y-0 opacity-100 scale-100"
      leave-to-class="translate-y-4 opacity-0 scale-95"
    >
      <div
        v-if="isOpen"
        class="fixed bottom-[5.5rem] right-6 z-50 w-96 max-w-[calc(100vw-2rem)] rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 flex flex-col overflow-hidden"
        style="height: min(500px, 70vh)"
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-4 py-3 bg-primary text-white shrink-0">
          <div class="flex items-center gap-2.5">
            <!-- NetLedger logo / robot icon -->
            <div class="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1.27A7.003 7.003 0 0113 23h-2a7.003 7.003 0 01-6.73-5H3a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73A2.002 2.002 0 0112 2zm-3 12a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/>
              </svg>
            </div>
            <div>
              <div class="flex items-center gap-2">
                <span class="font-semibold text-sm">NetLedger AI Support</span>
                <span class="px-1.5 py-0.5 text-[10px] font-bold bg-white/20 rounded">AI</span>
              </div>
              <span class="text-[11px] text-white/70">Ask anything about NetLedger</span>
            </div>
          </div>
          <button
            @click="closeChat"
            class="w-8 h-8 rounded-lg hover:bg-white/20 flex items-center justify-center transition-colors"
            aria-label="Close chat"
          >
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Messages Area -->
        <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          <!-- Welcome message when empty -->
          <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center px-4">
            <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3">
              <svg class="w-6 h-6 text-primary" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1.27A7.003 7.003 0 0113 23h-2a7.003 7.003 0 01-6.73-5H3a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73A2.002 2.002 0 0112 2zm-3 12a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/>
              </svg>
            </div>
            <p class="text-sm font-medium text-gray-700 dark:text-gray-300">Hi! How can I help you?</p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Ask me anything about NetLedger, billing, or MikroTik setup.</p>
          </div>

          <!-- Message bubbles -->
          <template v-for="msg in messages" :key="msg.id">
            <!-- AI message -->
            <div v-if="msg.role === 'assistant'" class="flex items-start gap-2">
              <div class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                <svg class="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1.27A7.003 7.003 0 0113 23h-2a7.003 7.003 0 01-6.73-5H3a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73A2.002 2.002 0 0112 2zm-3 12a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/>
                </svg>
              </div>
              <div class="max-w-[80%] px-3.5 py-2.5 rounded-2xl rounded-tl-md bg-gray-100 dark:bg-gray-700 text-sm text-gray-800 dark:text-gray-200 leading-relaxed whitespace-pre-wrap">
                {{ msg.content }}
              </div>
            </div>

            <!-- User message -->
            <div v-else class="flex justify-end">
              <div class="max-w-[80%] px-3.5 py-2.5 rounded-2xl rounded-tr-md bg-primary text-white text-sm leading-relaxed whitespace-pre-wrap">
                {{ msg.content }}
              </div>
            </div>
          </template>

          <!-- Typing indicator -->
          <div v-if="isTyping" class="flex items-start gap-2">
            <div class="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
              <svg class="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1.27A7.003 7.003 0 0113 23h-2a7.003 7.003 0 01-6.73-5H3a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73A2.002 2.002 0 0112 2zm-3 12a1.5 1.5 0 100 3 1.5 1.5 0 000-3zm6 0a1.5 1.5 0 100 3 1.5 1.5 0 000-3z"/>
              </svg>
            </div>
            <div class="px-4 py-3 rounded-2xl rounded-tl-md bg-gray-100 dark:bg-gray-700 flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce" style="animation-delay: 0ms" />
              <span class="w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce" style="animation-delay: 150ms" />
              <span class="w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce" style="animation-delay: 300ms" />
            </div>
          </div>
        </div>

        <!-- Image Attachments Preview -->
        <div v-if="attachedImages.length > 0" class="px-4 pb-2 flex gap-2 overflow-x-auto shrink-0">
          <div
            v-for="(img, idx) in attachedImages"
            :key="img.id"
            class="relative group shrink-0"
          >
            <a :href="img.url" target="_blank" rel="noopener">
              <img
                :src="img.url"
                :alt="img.name"
                class="w-16 h-16 rounded-lg object-cover border border-gray-200 dark:border-gray-600 hover:opacity-80 transition-opacity"
              />
            </a>
            <button
              @click="removeImage(idx)"
              class="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity shadow"
              aria-label="Remove image"
            >
              <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Input Area -->
        <div class="px-3 py-3 border-t border-gray-200 dark:border-gray-700 shrink-0">
          <div class="flex items-end gap-2">
            <!-- Image upload (tenant only) -->
            <button
              v-if="canUploadImages"
              @click="triggerImageUpload"
              :disabled="isSending"
              class="w-9 h-9 rounded-xl flex items-center justify-center text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-40 shrink-0"
              aria-label="Attach image"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              multiple
              class="hidden"
              @change="handleFileSelect"
            />

            <!-- Text input -->
            <textarea
              v-model="currentMessage"
              @keydown="handleKeydown"
              :disabled="isSending"
              rows="1"
              class="flex-1 resize-none rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary disabled:opacity-50 max-h-24 overflow-y-auto"
              placeholder="Type a message..."
              style="field-sizing: content"
            />

            <!-- Send button -->
            <button
              @click="sendMessage"
              :disabled="isSending || (!currentMessage.trim() && attachedImages.length === 0)"
              class="w-9 h-9 rounded-xl bg-primary text-white flex items-center justify-center hover:bg-primary-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
              aria-label="Send message"
            >
              <svg v-if="!isSending" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
              <!-- Spinner while sending -->
              <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
