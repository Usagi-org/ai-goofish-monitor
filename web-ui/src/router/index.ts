import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAuth } from '@/composables/useAuth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/tasks',
    children: [
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/TasksView.vue'),
        meta: { title: '任务管理', requiresAuth: true },
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('@/views/AccountsView.vue'),
        meta: { title: '账号管理', requiresAuth: true },
      },
      {
        path: 'results',
        name: 'Results',
        component: () => import('@/views/ResultsView.vue'),
        meta: { title: '结果查看', requiresAuth: true },
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('@/views/LogsView.vue'),
        meta: { title: '运行日志', requiresAuth: true },
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '系统设置', requiresAuth: true },
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

router.beforeEach((to, _from, next) => {
  const { isAuthenticated } = useAuth()
  
  // Set document title
  document.title = `${to.meta.title} - 闲鱼智能监控` || '闲鱼智能监控'

  if (to.meta.requiresAuth && !isAuthenticated.value) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && isAuthenticated.value) {
    next({ name: 'Tasks' })
  } else {
    next()
  }
})

export default router
