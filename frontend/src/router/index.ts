import { createRouter, createWebHistory } from 'vue-router'
import { isOnPremise } from '../composables/useDeploymentMode'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (_to.hash) return { el: _to.hash, behavior: 'smooth' }
    return { top: 0 }
  },
  routes: [
    {
      path: '/',
      component: () => isOnPremise ? import('../pages/Login.vue') : import('../pages/Landing.vue'),
    },
    {
      path: '/login',
      component: () => import('../pages/Login.vue'),
    },
    ...(!isOnPremise ? [{
      path: '/register',
      component: () => import('../pages/Register.vue'),
    }] : []),
    {
      path: '/self-hosted',
      component: () => import('../pages/SelfHosted.vue'),
    },
    {
      path: '/setup',
      component: () => import('../pages/Setup.vue'),
    },
    {
      path: '/setup-guide',
      component: () => import('../pages/SetupGuide.vue'),
    },
    ...(isOnPremise ? [
      {
        path: '/portal/login',
        component: () => import('../pages/portal/PortalLogin.vue'),
      },
      {
        path: '/portal',
        component: () => import('../components/layout/PortalLayout.vue'),
        children: [
          { path: '', component: () => import('../pages/portal/PortalDashboard.vue') },
          { path: 'invoices', component: () => import('../pages/portal/PortalInvoices.vue') },
          { path: 'usage', component: () => import('../pages/portal/PortalUsage.vue') },
          { path: 'tickets', component: () => import('../pages/portal/PortalTickets.vue') },
          { path: 'tickets/:id', component: () => import('../pages/portal/PortalTicketDetail.vue') },
        ],
      },
    ] : []),
    {
      path: '/portal/:slug/login',
      component: () => import('../pages/portal/PortalLogin.vue'),
    },
    {
      path: '/portal/:slug',
      component: () => import('../components/layout/PortalLayout.vue'),
      children: [
        { path: '', component: () => import('../pages/portal/PortalDashboard.vue') },
        { path: 'invoices', component: () => import('../pages/portal/PortalInvoices.vue') },
        { path: 'usage', component: () => import('../pages/portal/PortalUsage.vue') },
        { path: 'tickets', component: () => import('../pages/portal/PortalTickets.vue') },
        { path: 'tickets/:id', component: () => import('../pages/portal/PortalTicketDetail.vue') },
      ],
    },
    {
      path: '/dashboard',
      component: () => import('../components/layout/AppLayout.vue'),
      children: [
        { path: '', component: () => import('../pages/DashboardRouter.vue') },
        { path: '/customers', component: () => import('../pages/customers/CustomerList.vue') },
        { path: '/customers/:id', component: () => import('../pages/customers/CustomerDetail.vue') },
        { path: '/plans', component: () => import('../pages/Plans.vue') },
        { path: '/billing/invoices', component: () => import('../pages/billing/Invoices.vue') },
        { path: '/billing/payments', component: () => import('../pages/billing/Payments.vue') },
        { path: '/billing/expenses', component: () => import('../pages/Expenses.vue') },
        { path: '/hotspot/vouchers', component: () => import('../pages/Vouchers.vue') },
        { path: '/active-users', component: () => import('../pages/ActiveUsers.vue') },
        { path: '/hotspot', component: () => import('../pages/Hotspot.vue') },
        { path: '/routers', component: () => import('../pages/Routers.vue') },
        { path: '/areas', component: () => import('../pages/Areas.vue') },
        { path: '/tickets', component: () => import('../pages/Tickets.vue') },
        { path: '/tickets/:id', component: () => import('../pages/TicketDetail.vue') },
        { path: '/system/users', component: () => import('../pages/system/Users.vue') },
        { path: '/ipam', component: () => import('../pages/IPAM.vue') },
        { path: '/map', component: () => import('../pages/Map.vue') },
        { path: '/settings', component: () => import('../pages/Settings.vue') },
        { path: '/audit-logs', component: () => import('../pages/AuditLogs.vue') },
        { path: '/system/status', component: () => import('../pages/system/SystemStatus.vue') },
        { path: '/system/logs', component: () => import('../pages/system/Logs.vue') },
        { path: '/system/organizations', component: () => import('../pages/system/Organizations.vue') },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const publicPaths = ['/', '/login', '/register', '/self-hosted', '/setup', '/setup-guide']
  const isPortal = to.path.startsWith('/portal')
  const isPortalLogin = to.matched.some(r => r.path === '/portal/:slug/login') || (isOnPremise && to.path === '/portal/login')
  if (publicPaths.includes(to.path) || isPortalLogin) {
    // On-premise: redirect to setup if unconfigured
    if (isOnPremise && to.path !== '/setup' && !localStorage.getItem('setup_done')) {
      try {
        const resp = await fetch('/api/v1/setup/status')
        const data = await resp.json()
        if (!data.configured) return '/setup'
        localStorage.setItem('setup_done', '1')
      } catch { /* allow navigation */ }
    }
    return true
  }
  if (isPortal) {
    if (!localStorage.getItem('portal_token')) {
      if (isOnPremise) return '/portal/login'
      const slug = to.params.slug as string
      return slug ? `/portal/${slug}/login` : '/'
    }
  } else {
    if (!localStorage.getItem('access_token')) return '/login'
  }
  return true
})

export default router
