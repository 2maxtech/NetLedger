<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { useImpersonate } from '../../composables/useImpersonate'
import { useToast } from '../../composables/useToast'
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'
import ChatWidget from '../ChatWidget.vue'

const { user, isLoading, isAuthenticated, init } = useAuth()
const { impersonating, isImpersonating, exitOrg } = useImpersonate()
const { message: toastMessage, visible: toastVisible } = useToast()
const router = useRouter()

// Mobile sidebar
const isMobile = ref(window.innerWidth < 768)
const sidebarOpen = ref(false)

let resizeTimer: ReturnType<typeof setTimeout>
function onResize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    isMobile.value = window.innerWidth < 768
    if (!isMobile.value) sidebarOpen.value = false
  }, 150)
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  await init()
  if (!isAuthenticated.value) {
    router.push('/login')
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  clearTimeout(resizeTimer)
})

function handleExit() {
  exitOrg()
  router.push('/dashboard')
}
</script>

<template>
  <div v-if="isLoading" class="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
    <div class="flex flex-col items-center gap-3">
      <div class="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      <span class="text-sm text-gray-500 dark:text-gray-400">Loading...</span>
    </div>
  </div>
  <div v-else class="flex flex-col h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <!-- Demo banner -->
    <div v-if="user?.is_demo" class="bg-gradient-to-r from-amber-500 to-orange-500 text-white text-center py-2 px-4 text-sm font-medium shrink-0">
      You're exploring the demo &mdash;
      <router-link to="/register" class="underline font-bold ml-1">Sign Up Free</router-link>
      to manage your ISP
    </div>
    <div class="flex flex-1 overflow-hidden">
    <!-- Desktop sidebar (normal flow) -->
    <Sidebar v-if="!isMobile" />

    <!-- Mobile sidebar (overlay) -->
    <Sidebar v-if="isMobile" :is-mobile="true" :is-open="sidebarOpen" @close="sidebarOpen = false" />

    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Mobile header bar with hamburger -->
      <div v-if="isMobile" class="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <button
          @click="sidebarOpen = true"
          class="p-1.5 rounded-lg text-[#e8700a] hover:bg-orange-50 dark:hover:bg-orange-950/30 transition-colors"
          aria-label="Open menu"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div class="flex items-center gap-2">
          <img src="/logo-2.png" alt="NetLedger" class="w-7 h-7 object-contain" />
          <span class="text-sm font-bold text-gray-800 dark:text-gray-200">NetLedger</span>
        </div>
        <div class="w-9" /> <!-- spacer to balance hamburger -->
      </div>

      <!-- Impersonation Banner -->
      <div v-if="isImpersonating" class="flex items-center justify-between px-4 py-2 bg-primary text-white text-sm shrink-0">
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clip-rule="evenodd"/></svg>
          <span>Managing: <strong>{{ impersonating?.company_name }}</strong> ({{ impersonating?.username }})</span>
        </div>
        <button @click="handleExit" class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/20 hover:bg-white/30 text-xs font-medium transition-colors">
          <svg class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z" clip-rule="evenodd"/><path fill-rule="evenodd" d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z" clip-rule="evenodd"/></svg>
          Exit to Platform
        </button>
      </div>
      <Header v-if="!isMobile" />
      <main class="flex-1 overflow-y-auto p-4 md:p-6 bg-gray-50 dark:bg-gray-900">
        <router-view />
      </main>
    </div>
    </div>

    <!-- Toast notification -->
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="translate-y-4 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-4 opacity-0"
    >
      <div v-if="toastVisible" class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-amber-500 text-white px-6 py-3 rounded-xl shadow-2xl text-sm font-medium flex items-center gap-3 max-w-md">
        <svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z"/></svg>
        {{ toastMessage }}
      </div>
    </Transition>

    <!-- AI Chat Widget (tenant admins only, not demo, not super_admin) -->
    <ChatWidget v-if="isAuthenticated && !user?.is_demo && user?.role !== 'super_admin'" mode="tenant" />
  </div>
</template>
