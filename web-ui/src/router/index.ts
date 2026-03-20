import { watch } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAuth } from '@/composables/useAuth'
import { i18n, t } from '@/i18n'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { titleKey: 'routes.login' },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { titleKey: 'routes.dashboard', requiresAuth: true },
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/TasksView.vue'),
        meta: { titleKey: 'routes.tasks', requiresAuth: true },
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/AccountsView.vue'),
        meta: { titleKey: 'routes.accounts', requiresAuth: true },
      },
      {
        path: 'results',
        name: 'Results',
        component: () => import('@/views/ResultsView.vue'),
        meta: { titleKey: 'routes.results', requiresAuth: true },
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogsView.vue'),
        meta: { titleKey: 'routes.logs', requiresAuth: true },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { titleKey: 'routes.settings', requiresAuth: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function updateDocumentTitle() {
  const currentRoute = router.currentRoute.value
  const titleKey = typeof currentRoute.meta.titleKey === 'string'
    ? currentRoute.meta.titleKey
    : null
  const appName = t('app.name')
  document.title = titleKey ? `${t(titleKey)} - ${appName}` : appName
}

router.beforeEach((to, _from, next) => {
  const { isAuthenticated } = useAuth()

  if (to.meta.requiresAuth && !isAuthenticated.value) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && isAuthenticated.value) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

router.afterEach(() => {
  updateDocumentTitle()
})

watch(
  () => i18n.global.locale.value,
  () => {
    updateDocumentTitle()
  },
)

export default router
