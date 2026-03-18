import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: Dashboard,
    },
    {
      path: '/analysis',
      name: 'analysis',
      component: () => import('@/views/Analysis.vue'),
    },
    {
      path: '/scanner',
      name: 'scanner',
      component: () => import('@/views/Scanner.vue'),
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('@/views/Backtest.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/Settings.vue'),
    },
  ],
})

export default router
