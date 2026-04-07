<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { useImpersonate } from '../../composables/useImpersonate'
import { isOnPremise } from '../../composables/useDeploymentMode'
import { useTheme } from '../../composables/useTheme'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const { user } = useAuth()
const { isImpersonating } = useImpersonate()
const { isDark, toggle: toggleTheme } = useTheme()
const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
const showAdminMenu = computed(() => isOnPremise || !isSuperAdmin.value || isImpersonating.value)

const icons: Record<string, string> = {
  dashboard: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1"/>',
  users: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>',
  package: '<path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>',
  receipt: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"/>',
  wifi: '<path stroke-linecap="round" stroke-linejoin="round" d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z"/>',
  hotspot: '<path stroke-linecap="round" stroke-linejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.047 8.287 8.287 0 009 9.601a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 18a3.75 3.75 0 00.495-7.468 5.99 5.99 0 00-1.925 3.547 5.975 5.975 0 01-2.133-1.001A3.75 3.75 0 0012 18z"/>',
  server: '<path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z"/>',
  'map-pin': '<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"/>',
  ticket: '<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z"/>',
  guide: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>',
  settings: '<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>',
}

type MenuItem = { path?: string; label: string; icon: string; children?: { path: string; label: string }[] }

const ispMenu: MenuItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { path: '/customers', label: 'Customers', icon: 'users' },
  { path: '/plans', label: 'Plans', icon: 'package' },
  {
    label: 'Billing', icon: 'receipt', children: [
      { path: '/billing/invoices', label: 'Invoices' },
      { path: '/billing/payments', label: 'Payments' },
      { path: '/billing/expenses', label: 'Expenses' },
    ]
  },
  { path: '/active-users', label: 'Active Users', icon: 'wifi' },
  {
    label: 'Hotspot', icon: 'hotspot', children: [
      { path: '/hotspot', label: 'Users & Sessions' },
      { path: '/hotspot/vouchers', label: 'Vouchers' },
    ]
  },
  { path: '/routers', label: 'Routers', icon: 'server' },
  { path: '/areas', label: 'Areas', icon: 'map-pin' },
  { path: '/tickets', label: 'Tickets', icon: 'ticket' },
  {
    label: 'System', icon: 'settings', children: [
      { path: '/system/users', label: 'Staff Users' },
      { path: '/ipam', label: 'IPAM' },
      { path: '/settings', label: 'Settings' },
      { path: '/audit-logs', label: 'Audit Logs' },
      { path: '/system/status', label: 'System Status' },
      { path: '/system/logs', label: 'Logs' },
    ]
  },
]

const superAdminMenu: MenuItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: 'dashboard' },
  { path: '/system/organizations', label: 'Organizations', icon: 'users' },
  { path: '/system/status', label: 'System Status', icon: 'server' },
  { path: '/settings', label: 'Settings', icon: 'settings' },
]

const menuItems = computed(() => showAdminMenu.value ? ispMenu : superAdminMenu)

const openMenus = ref<string[]>(['Billing', 'Hotspot', 'System'])

function toggleMenu(label: string) {
  const idx = openMenus.value.indexOf(label)
  if (idx >= 0) openMenus.value.splice(idx, 1)
  else openMenus.value.push(label)
}

function isActive(path: string) {
  return route.path === path
}

function navigate(path: string) {
  router.push(path)
}
</script>

<template>
  <aside
    :class="[
      'flex flex-col h-screen bg-sidebar text-gray-300 transition-all duration-300 shrink-0',
      collapsed ? 'w-16' : 'w-56'
    ]"
  >
    <!-- Logo -->
    <div class="flex items-center gap-3 px-4 py-5">
      <img src="/logo-2.png" alt="NetLedger" class="w-12 h-12 object-contain" />
      <div v-if="!collapsed">
        <span class="text-white font-bold text-lg block leading-tight">NetLedger</span>
        <span class="text-[10px] text-gray-500 font-medium">by 2max.tech</span>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
      <template v-for="item in menuItems" :key="item.label">
        <!-- Parent with children -->
        <template v-if="item.children">
          <button
            @click="toggleMenu(item.label)"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              'hover:bg-sidebar-hover hover:text-white'
            ]"
          >
            <svg class="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" v-html="icons[item.icon]" />
            <span v-if="!collapsed" class="flex-1 text-left">{{ item.label }}</span>
            <svg v-if="!collapsed" class="w-4 h-4 transition-transform" :class="{ 'rotate-90': openMenus.includes(item.label) }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
          </button>
          <div v-if="openMenus.includes(item.label) && !collapsed" class="ml-4 space-y-0.5">
            <button
              v-for="child in item.children"
              :key="child.path"
              @click="navigate(child.path)"
              :class="[
                'w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                isActive(child.path!)
                  ? 'bg-sidebar-active text-primary font-medium'
                  : 'text-gray-400 hover:bg-sidebar-hover hover:text-white'
              ]"
            >
              <span class="w-1.5 h-1.5 rounded-full" :class="isActive(child.path!) ? 'bg-primary' : 'bg-gray-600'" />
              {{ child.label }}
            </button>
          </div>
        </template>

        <!-- Single item -->
        <template v-else>
          <button
            @click="navigate(item.path!)"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive(item.path!)
                ? 'bg-sidebar-active text-white border-l-2 border-primary'
                : 'hover:bg-sidebar-hover hover:text-white'
            ]"
          >
            <svg class="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" v-html="icons[item.icon]" />
            <span v-if="!collapsed">{{ item.label }}</span>
          </button>
        </template>
      </template>
    </nav>

    <!-- Theme toggle -->
    <button
      @click="toggleTheme"
      class="flex items-center gap-3 px-3 py-2 mx-2 rounded-lg text-sm font-medium hover:bg-sidebar-hover hover:text-white transition-colors"
      :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
    >
      <!-- Sun icon (shown in dark mode) -->
      <svg v-if="isDark" class="w-5 h-5 shrink-0 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="5"/>
        <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
        <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
      </svg>
      <!-- Moon icon (shown in light mode) -->
      <svg v-else class="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
      </svg>
      <span v-if="!collapsed">{{ isDark ? 'Light Mode' : 'Dark Mode' }}</span>
    </button>

    <!-- Collapse toggle -->
    <button
      @click="collapsed = !collapsed"
      class="flex items-center justify-center py-3 border-t border-white/10 hover:bg-sidebar-hover transition-colors"
    >
      <svg class="w-5 h-5 transition-transform" :class="{ 'rotate-180': collapsed }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>
    </button>
  </aside>
</template>
