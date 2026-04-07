<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { demoLogin } from '../api/auth'

const router = useRouter()
const demoLoading = ref(false)

function loadTawk() {
  if (document.getElementById('tawk-script')) return
  const s = document.createElement('script')
  s.id = 'tawk-script'
  s.async = true
  s.src = 'https://embed.tawk.to/69d550e59922e51c34efc32a/1jlkk80jn'
  s.charset = 'UTF-8'
  s.setAttribute('crossorigin', '*')
  document.body.appendChild(s)
}

function unloadTawk() {
  const el = document.getElementById('tawk-script')
  if (el) el.remove()
  // Hide the widget if it's been loaded
  if (window.Tawk_API?.hideWidget) window.Tawk_API.hideWidget()
}

onMounted(() => {
  if (localStorage.getItem('access_token')) {
    router.replace('/dashboard')
  }
  loadTawk()
  if (window.Tawk_API?.showWidget) window.Tawk_API.showWidget()
})

onUnmounted(() => {
  unloadTawk()
})

async function tryDemo() {
  demoLoading.value = true
  try {
    const { data } = await demoLogin()
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    router.push('/dashboard')
  } catch {
    // Demo not available — silently ignore
  } finally {
    demoLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-white">
    <!-- Navbar -->
    <nav class="fixed top-0 w-full bg-white/80 backdrop-blur-md border-b border-gray-100 z-50">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 h-14 sm:h-16 flex items-center justify-between">
        <div class="flex items-center gap-2 sm:gap-3">
          <img src="/logo-2.png" class="w-7 h-7 sm:w-9 sm:h-9" alt="NetLedger" />
          <div class="flex flex-col -space-y-1">
            <span class="text-base sm:text-xl font-bold text-gray-900">NetLedger</span>
            <span class="text-[9px] sm:text-[10px] text-gray-400 font-medium">by 2max.tech</span>
          </div>
        </div>
        <div class="flex items-center gap-2 sm:gap-3">
          <router-link to="/self-hosted" class="hidden sm:inline-flex px-5 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
            Self-Hosted
          </router-link>
          <router-link to="/setup-guide" class="hidden sm:inline-flex px-5 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors">
            Setup Guide
          </router-link>
          <router-link to="/register" class="hidden sm:inline-flex px-5 py-2 text-sm font-medium text-primary border border-primary hover:bg-primary/5 rounded-lg transition-colors">
            Register
          </router-link>
          <router-link to="/login" class="px-3 sm:px-5 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-white bg-primary hover:bg-primary-hover rounded-lg transition-colors">
            Login
          </router-link>
        </div>
      </div>
    </nav>

    <!-- Hero -->
    <section class="pt-24 sm:pt-32 pb-12 sm:pb-20 px-4 sm:px-6">
      <div class="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        <div>
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-green-500/10 text-green-600 text-xs font-medium mb-4 sm:mb-6">
            <span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Free During Beta
          </div>
          <h1 class="text-3xl sm:text-5xl font-bold text-gray-900 leading-tight">
            Manage your ISP<br />
            <span class="text-primary">with confidence</span>
          </h1>
          <p class="text-base sm:text-lg text-gray-500 mt-4 sm:mt-6 leading-relaxed max-w-lg">
            NetLedger is a complete billing, subscriber management, and MikroTik integration platform built for Internet Service Providers.
          </p>
          <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4 mt-6 sm:mt-8">
            <router-link to="/register" class="px-6 py-3 text-sm font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl shadow-lg shadow-primary/25 transition-all hover:-translate-y-0.5 text-center">
              Join the Beta — It's Free
            </router-link>
            <button @click="tryDemo" :disabled="demoLoading" class="px-6 py-3 text-sm font-semibold text-primary border-2 border-primary hover:bg-primary/5 rounded-xl transition-colors text-center disabled:opacity-50">
              {{ demoLoading ? 'Loading...' : 'Try Demo' }}
            </button>
          </div>
          <div class="flex flex-wrap items-center gap-4 sm:gap-6 mt-8 sm:mt-10 text-sm text-gray-400">
            <div class="flex items-center gap-2">
              <svg class="w-4 h-4 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              MikroTik Ready
            </div>
            <div class="flex items-center gap-2">
              <svg class="w-4 h-4 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              Auto Billing
            </div>
            <div class="flex items-center gap-2">
              <svg class="w-4 h-4 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg>
              Multi-Router
            </div>
          </div>
        </div>
        <!-- Hero visual -->
        <div class="relative hidden lg:block">
          <div class="rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 p-6 shadow-2xl shadow-gray-200/50">
            <div class="rounded-xl bg-white border border-gray-100 p-5 space-y-4">
              <div class="flex items-center gap-3 mb-4">
                <img src="/logo-2.png" class="w-7 h-7" />
                <span class="font-bold text-gray-800 text-sm">NetLedger Dashboard</span>
                <span class="ml-auto px-2 py-0.5 text-[10px] font-medium bg-green-100 text-green-700 rounded-full">Live</span>
              </div>
              <div class="grid grid-cols-3 gap-3">
                <div class="rounded-lg bg-orange-50 border border-orange-100 p-3">
                  <p class="text-[10px] text-orange-600 font-medium">Subscribers</p>
                  <p class="text-lg font-bold text-gray-900">248</p>
                </div>
                <div class="rounded-lg bg-green-50 border border-green-100 p-3">
                  <p class="text-[10px] text-green-600 font-medium">Active</p>
                  <p class="text-lg font-bold text-gray-900">231</p>
                </div>
                <div class="rounded-lg bg-blue-50 border border-blue-100 p-3">
                  <p class="text-[10px] text-blue-600 font-medium">Online</p>
                  <p class="text-lg font-bold text-gray-900">189</p>
                </div>
              </div>
              <div class="flex gap-2">
                <div class="flex-1 h-2 rounded-full bg-green-500" />
                <div class="w-6 h-2 rounded-full bg-amber-400" />
                <div class="w-3 h-2 rounded-full bg-red-400" />
              </div>
              <div class="space-y-2">
                <div class="flex items-center justify-between text-xs">
                  <span class="text-gray-500">MikroTik-Main</span>
                  <span class="text-green-600 font-medium">Connected</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                  <span class="text-gray-500">MRR</span>
                  <span class="text-gray-900 font-semibold">&#8369;186,752</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                  <span class="text-gray-500">Collection Rate</span>
                  <span class="text-gray-900 font-semibold">94.2%</span>
                </div>
              </div>
            </div>
          </div>
          <div class="absolute -bottom-4 -right-4 w-32 h-32 rounded-full bg-primary/5 -z-10" />
          <div class="absolute -top-4 -left-4 w-24 h-24 rounded-full bg-amber-500/5 -z-10" />
        </div>
      </div>
    </section>

    <!-- Features -->
    <section id="features" class="py-12 sm:py-20 px-4 sm:px-6 bg-gray-50">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-10 sm:mb-14">
          <h2 class="text-2xl sm:text-3xl font-bold text-gray-900">Everything you need to run your ISP</h2>
          <p class="text-gray-500 mt-3 max-w-2xl mx-auto text-sm sm:text-base">From subscriber provisioning to billing automation, NetLedger handles it all with native MikroTik integration.</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <!-- Feature cards -->
          <div v-for="feature in features" :key="feature.title" class="rounded-xl bg-white border border-gray-100 p-6 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200">
            <div :class="['w-10 h-10 rounded-lg flex items-center justify-center mb-4', feature.bg]">
              <svg class="w-5 h-5" :class="feature.icon_color" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" v-html="feature.icon" />
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">{{ feature.title }}</h3>
            <p class="text-sm text-gray-500 leading-relaxed">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- How It Works -->
    <section class="py-12 sm:py-20 px-4 sm:px-6">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-10 sm:mb-14">
          <h2 class="text-2xl sm:text-3xl font-bold text-gray-900">How it works</h2>
          <p class="text-gray-500 mt-3">Get up and running in minutes</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div v-for="(step, i) in steps" :key="i" class="text-center">
            <div class="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-lg flex items-center justify-center mx-auto mb-4">
              {{ i + 1 }}
            </div>
            <h3 class="font-semibold text-gray-900 mb-2">{{ step.title }}</h3>
            <p class="text-sm text-gray-500">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Deployment Options -->
    <section class="py-12 sm:py-20 px-4 sm:px-6">
      <div class="max-w-6xl mx-auto">
        <div class="text-center mb-10 sm:mb-14">
          <h2 class="text-2xl sm:text-3xl font-bold text-gray-900">Choose your deployment</h2>
          <p class="text-gray-500 mt-3 text-sm sm:text-base">Use our cloud platform or install on your own server</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
          <div class="rounded-xl border-2 border-primary bg-primary/5 p-8">
            <div class="flex items-center gap-2 mb-4">
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary text-white">Recommended</span>
              <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">Free Beta</span>
            </div>
            <h3 class="text-xl font-bold text-gray-900">Cloud (SaaS)</h3>
            <p class="text-sm text-gray-500 mt-2">We host everything. Sign up and start managing your ISP — completely free during the beta period.</p>
            <ul class="mt-5 space-y-2.5 text-sm text-gray-600">
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> No server to maintain</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Automatic updates</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Secure VPN tunnel to your router</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> All features included — no limits</li>
            </ul>
            <router-link to="/register" class="mt-6 inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl transition-colors">
              Join the Beta — It's Free
            </router-link>
          </div>
          <div class="rounded-xl border border-primary/30 bg-primary/5 p-8 relative overflow-hidden">
            <div class="absolute top-0 right-0 bg-green-500 text-white text-[10px] font-bold px-6 py-1 rotate-45 translate-x-6 translate-y-3">LIVE</div>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 mb-4">Available Now</span>
            <h3 class="text-xl font-bold text-gray-900">On-Premise (Docker)</h3>
            <p class="text-sm text-gray-500 mt-2">Install on your own server. Full control, your data stays on your network.</p>
            <ul class="mt-5 space-y-2.5 text-sm text-gray-600">
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Router on same LAN — no VPN needed</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Data stays on your network</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> One-command Docker install</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Runs on x86 and ARM64 (Raspberry Pi)</li>
              <li class="flex items-start gap-2"><svg class="w-4 h-4 text-green-500 mt-0.5 shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clip-rule="evenodd"/></svg> Free during beta — no restrictions</li>
            </ul>
            <router-link to="/self-hosted" class="mt-6 inline-flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl transition-colors">
              Get Started — Self-Hosted
            </router-link>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="py-12 sm:py-20 px-4 sm:px-6 bg-gradient-to-br from-sidebar to-gray-900">
      <div class="max-w-3xl mx-auto text-center">
        <h2 class="text-2xl sm:text-3xl font-bold text-white">Ready to streamline your ISP operations?</h2>
        <p class="text-gray-400 mt-4 text-base sm:text-lg">Join the beta and get full access to every feature — completely free while we're in beta testing.</p>
        <div class="flex flex-col sm:flex-row items-stretch sm:items-center justify-center gap-3 sm:gap-4 mt-8">
          <router-link to="/register" class="px-8 py-3 text-sm font-semibold text-white bg-primary hover:bg-primary-hover rounded-xl shadow-lg shadow-primary/25 transition-all hover:-translate-y-0.5 text-center">
            Join the Beta — It's Free
          </router-link>
          <button @click="tryDemo" :disabled="demoLoading" class="px-8 py-3 text-sm font-semibold text-white border-2 border-white/30 hover:bg-white/10 rounded-xl transition-colors text-center disabled:opacity-50">
            {{ demoLoading ? 'Loading...' : 'Try Demo' }}
          </button>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="py-8 sm:py-10 px-4 sm:px-6 border-t border-gray-100">
      <div class="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-3">
          <img src="/logo-2.png" class="w-6 h-6" />
          <span class="text-sm font-semibold text-gray-700">NetLedger</span>
          <span class="text-sm text-gray-400">&mdash; by 2max Tech</span>
        </div>
        <p class="text-sm text-gray-400">&copy; {{ new Date().getFullYear() }} 2max Tech. All rights reserved.</p>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
const features = [
  {
    title: 'MikroTik Integration',
    desc: 'Auto-provision PPPoE accounts, manage bandwidth profiles, throttle or disconnect subscribers instantly via RouterOS REST API.',
    bg: 'bg-orange-100', icon_color: 'text-orange-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z"/>',
  },
  {
    title: 'Automated Billing',
    desc: 'Generate monthly invoices, track payments, auto-suspend overdue accounts with graduated enforcement — throttle first, then disconnect.',
    bg: 'bg-green-100', icon_color: 'text-green-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z"/>',
  },
  {
    title: 'Multi-Router Support',
    desc: 'Manage multiple MikroTik routers from one dashboard. Assign customers to routers by area or manually. Monitor health in real time.',
    bg: 'bg-blue-100', icon_color: 'text-blue-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M8.288 15.038a5.25 5.25 0 017.424 0M5.106 11.856c3.807-3.808 9.98-3.808 13.788 0M1.924 8.674c5.565-5.565 14.587-5.565 20.152 0M12.53 18.22l-.53.53-.53-.53a.75.75 0 011.06 0z"/>',
  },
  {
    title: 'Customer Portal',
    desc: 'Subscribers can view invoices, check usage, track PPPoE sessions, and open support tickets through a self-service portal.',
    bg: 'bg-purple-100', icon_color: 'text-purple-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>',
  },
  {
    title: 'Prepaid Vouchers',
    desc: 'Generate batch voucher codes, redeem for subscribers, and manage expiration. Perfect for prepaid WiFi or promotional offers.',
    bg: 'bg-amber-100', icon_color: 'text-amber-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z"/>',
  },
  {
    title: 'Expense Tracking',
    desc: 'Track ISP expenses by category — fiber uplink, power, equipment, salaries. Get a clear picture of your operating costs.',
    bg: 'bg-red-100', icon_color: 'text-red-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/>',
  },
  {
    title: 'Support Tickets',
    desc: 'Built-in ticketing system with priority levels, staff assignment, and a chat-style message thread for each ticket.',
    bg: 'bg-cyan-100', icon_color: 'text-cyan-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155"/>',
  },
  {
    title: 'IP Address Management',
    desc: 'Manage IP pools per router, track subnet allocations, and assign address ranges for PPPoE and static IP customers.',
    bg: 'bg-indigo-100', icon_color: 'text-indigo-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M14.25 9.75L16.5 12l-2.25 2.25m-4.5 0L7.5 12l2.25-2.25M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"/>',
  },
  {
    title: 'Audit Logging',
    desc: 'Every action is logged — customer changes, billing operations, network actions. Full accountability and compliance trail.',
    bg: 'bg-gray-100', icon_color: 'text-gray-600',
    icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"/>',
  },
]

const steps = [
  {
    title: 'Add Your Router',
    desc: 'Enter your MikroTik router credentials. NetLedger connects via REST API and imports existing PPPoE subscribers automatically.',
  },
  {
    title: 'Create Plans & Customers',
    desc: 'Set up bandwidth plans with pricing. Add customers and NetLedger auto-provisions PPPoE secrets and profiles on MikroTik.',
  },
  {
    title: 'Bill & Collect',
    desc: 'Generate invoices monthly, record payments, and let automated enforcement handle overdue accounts — throttle, then disconnect.',
  },
]
</script>
