<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPortalTicketCounts } from '../../api/portal'

const route = useRoute()
const router = useRouter()
const slug = computed(() => route.params.slug as string)

const customer = computed(() => {
  const raw = localStorage.getItem('portal_customer')
  return raw ? JSON.parse(raw) : null
})

const openTicketCount = ref(0)

async function fetchTicketCounts() {
  try {
    const { data } = await getPortalTicketCounts()
    openTicketCount.value = data.open
  } catch { /* ignore */ }
}

onMounted(fetchTicketCounts)
setInterval(fetchTicketCounts, 60_000)

function logout() {
  localStorage.removeItem('portal_token')
  localStorage.removeItem('portal_customer')
  localStorage.removeItem('portal_slug')
  router.push(`/portal/${slug.value}/login`)
}

const navItems = computed(() => [
  { path: `/portal/${slug.value}`, label: 'Dashboard', exact: true },
  { path: `/portal/${slug.value}/invoices`, label: 'Invoices' },
  { path: `/portal/${slug.value}/usage`, label: 'Usage' },
  { path: `/portal/${slug.value}/tickets`, label: 'Tickets', badge: openTicketCount.value },
])

function isActive(item: { path: string; exact?: boolean }) {
  return item.exact ? route.path === item.path : route.path.startsWith(item.path)
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Top nav -->
    <header class="bg-white border-b border-gray-200">
      <div class="max-w-5xl mx-auto px-4 flex items-center justify-between h-14">
        <div class="flex items-center gap-3">
          <img src="/logo-2.png" class="w-7 h-7" />
          <div>
            <span class="font-bold text-gray-800 block leading-tight">NetLedger</span>
            <span class="text-[10px] text-gray-400 font-medium">by 2max.tech</span>
          </div>
        </div>
        <div class="flex items-center gap-6">
          <nav class="flex gap-1">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              :class="[
                'relative px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                isActive(item)
                  ? 'bg-primary/10 text-primary'
                  : 'text-gray-600 hover:bg-gray-100'
              ]"
            >
              {{ item.label }}
              <span v-if="item.badge && item.badge > 0" class="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold leading-none rounded-full bg-red-500 text-white">{{ item.badge }}</span>
            </router-link>
          </nav>
          <div class="flex items-center gap-2">
            <span class="text-sm text-gray-600">{{ customer?.full_name }}</span>
            <button @click="logout()" class="text-sm text-red-600 hover:text-red-700">Logout</button>
          </div>
        </div>
      </div>
    </header>
    <main class="max-w-5xl mx-auto px-4 py-6">
      <router-view />
    </main>
  </div>
</template>
