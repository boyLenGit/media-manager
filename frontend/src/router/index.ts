import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/api/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/setup',
    name: 'setup',
    component: () => import('@/views/Setup.vue'),
    meta: { public: true, title: '初始化' },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '总览' },
      },
      {
        path: 'library',
        name: 'library',
        component: () => import('@/views/Library.vue'),
        meta: { title: '资源库' },
      },
      {
        path: 'duplicates',
        name: 'duplicates',
        component: () => import('@/views/Duplicates.vue'),
        meta: { title: '重复检测' },
      },
      {
        path: 'media/:id',
        name: 'media-detail',
        component: () => import('@/views/MediaDetail.vue'),
        meta: { title: '资源详情' },
      },
      {
        path: 'search',
        name: 'search',
        component: () => import('@/views/Search.vue'),
        meta: { title: '搜索' },
      },
      {
        path: 'downloads',
        name: 'downloads',
        component: () => import('@/views/Downloads.vue'),
        meta: { title: '下载' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '设置' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // 公开路由直接放行
  if (to.meta.public) {
    // 已登录访问 login/setup 直接跳首页
    if (auth.isAuthenticated && (to.name === 'login' || to.name === 'setup')) {
      return { name: 'dashboard' }
    }
    return true
  }

  // 未登录:先看是不是 setup 阶段
  if (!auth.isAuthenticated) {
    try {
      const { setup_required } = await authApi.setupRequired()
      return setup_required
        ? { name: 'setup' }
        : { name: 'login', query: { redirect: to.fullPath } }
    } catch {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  // 已登录但 user 信息缺失,补一次
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.clearTokens()
      return { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

router.afterEach((to) => {
  const title = (to.meta?.title as string | undefined) || ''
  document.title = title ? `${title} · MediaHub` : 'MediaHub'
})

export default router
