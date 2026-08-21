<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer,
  FolderOpened,
  User,
  Search,
  Download,
  Setting,
  Connection,
  ArrowDown,
  SwitchButton,
  CopyDocument,
  DArrowLeft,
  DArrowRight,
  Menu as MenuIcon,
} from '@element-plus/icons-vue'
import { systemApi, type AppInfo } from '@/api/system'
import { setAuthFailureHandler } from '@/api/http'
import { useAuthStore } from '@/store/auth'
import { searchApi, type LocalSearchHit } from '@/api/search'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ============================================================
// 响应式断点
// ============================================================
// 768px 以下视为移动端,sidebar 完全折叠成抽屉,header 显示汉堡菜单
const MOBILE_BREAKPOINT = 768
const isMobile = ref(window.innerWidth < MOBILE_BREAKPOINT)
const onResize = () => {
  isMobile.value = window.innerWidth < MOBILE_BREAKPOINT
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

// ============================================================
// 桌面端 sidebar 折叠态(localStorage 持久)
// ============================================================
const COLLAPSE_KEY = 'media-manager.sidebar.collapse'
const collapse = ref(localStorage.getItem(COLLAPSE_KEY) === '1')
const toggleCollapse = () => {
  collapse.value = !collapse.value
  localStorage.setItem(COLLAPSE_KEY, collapse.value ? '1' : '0')
}

// ============================================================
// 移动端 drawer 抽屉
// ============================================================
const drawerVisible = ref(false)
// 路由跳转后自动关抽屉
watch(
  () => route.path,
  () => {
    if (drawerVisible.value) drawerVisible.value = false
  },
)

const info = ref<AppInfo | null>(null)
const healthy = ref<boolean | null>(null)

// ============================================================
// 全局搜索
// ============================================================
const globalQ = ref('')
const globalHits = ref<LocalSearchHit[]>([])
const searching = ref(false)
let searchTimer: number | null = null

const onGlobalQuery = (query: string, cb: (hits: any[]) => void) => {
  if (!query) {
    cb([])
    return
  }
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(async () => {
    searching.value = true
    try {
      const r = await searchApi.searchLocal(query, 20)
      globalHits.value = r.hits
      cb(
        r.hits.map((h) => ({
          value: h.title,
          ...h,
        })),
      )
    } catch {
      cb([])
    } finally {
      searching.value = false
    }
  }, 200)
}

const onGlobalSelect = (item: any) => {
  if (item.media_item_id) {
    router.push(`/media/${item.media_item_id}`)
    globalQ.value = ''
  }
}

const activeMenu = computed(() => route.path)

const navItems = [
  { path: '/', label: '总览', icon: Odometer },
  { path: '/library', label: '资源库', icon: FolderOpened },
  { path: '/authors', label: '作者', icon: User },
  { path: '/duplicates', label: '重复检测', icon: CopyDocument },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/downloads', label: '下载', icon: Download },
  { path: '/settings', label: '设置', icon: Setting },
]

const handleSelect = (path: string) => {
  router.push(path)
  drawerVisible.value = false
}

const handleUserCmd = async (cmd: string) => {
  if (cmd === 'logout') {
    await auth.logout()
    router.replace('/login')
  }
}

onMounted(async () => {
  setAuthFailureHandler(() => {
    auth.clearTokens()
    router.replace('/login')
  })

  try {
    const [h, i] = await Promise.all([systemApi.health(), systemApi.info()])
    healthy.value = h.status === 'ok'
    info.value = i
  } catch {
    healthy.value = false
  }
})
</script>

<template>
  <el-container class="layout-root">
    <!-- 桌面端 sidebar (移动端隐藏) -->
    <el-aside
      v-if="!isMobile"
      :width="collapse ? '64px' : '220px'"
      class="layout-aside"
    >
      <div class="brand">
        <el-icon :size="22"><Connection /></el-icon>
        <span v-if="!collapse" class="brand-name">Media Manager</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapse"
        :router="false"
        background-color="#1f2937"
        text-color="#cbd5e1"
        active-text-color="#60a5fa"
        @select="handleSelect"
      >
        <el-menu-item v-for="n in navItems" :key="n.path" :index="n.path">
          <el-icon><component :is="n.icon" /></el-icon>
          <template #title>{{ n.label }}</template>
        </el-menu-item>
      </el-menu>
      <div
        class="aside-collapse"
        @click="toggleCollapse"
        :title="collapse ? '展开侧栏' : '收起侧栏'"
      >
        <el-icon :size="16">
          <component :is="collapse ? DArrowRight : DArrowLeft" />
        </el-icon>
      </div>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <!-- 移动端汉堡菜单 -->
          <el-button
            v-if="isMobile"
            text
            class="mobile-menu-btn"
            @click="drawerVisible = true"
          >
            <el-icon :size="20"><MenuIcon /></el-icon>
          </el-button>
          <span class="page-title">{{ route.meta.title }}</span>
        </div>

        <el-autocomplete
          v-model="globalQ"
          :fetch-suggestions="onGlobalQuery"
          placeholder="快速搜索…"
          :prefix-icon="Search"
          clearable
          class="global-search"
          value-key="value"
          @select="onGlobalSelect"
        >
          <template #default="{ item }">
            <div class="search-suggest">
              <div class="s-title">{{ item.title }}</div>
              <div class="s-meta" v-if="item.author_name || item.tag_names">
                <span v-if="item.author_name">{{ item.author_name }}</span>
                <span v-if="item.tag_names" class="muted">{{ item.tag_names }}</span>
              </div>
            </div>
          </template>
        </el-autocomplete>

        <div class="header-right">
          <!-- 移动端只显示状态点,不显示文字标签 -->
          <span
            v-if="isMobile && healthy !== null"
            class="health-dot"
            :class="{ ok: healthy, bad: !healthy }"
            :title="healthy ? '后端在线' : '后端离线'"
          />
          <template v-else>
            <el-tag v-if="healthy === true" type="success" size="small">后端在线</el-tag>
            <el-tag v-else-if="healthy === false" type="danger" size="small">后端离线</el-tag>
            <el-tag v-if="info?.qbittorrent_configured" type="info" size="small">qB</el-tag>
            <el-tag v-if="info?.jellyfin_configured" type="info" size="small">Jellyfin</el-tag>
          </template>

          <el-dropdown trigger="click" @command="handleUserCmd">
            <span class="user-trigger">
              <span class="user-name">
                {{ auth.user?.display_name || auth.user?.username || '...' }}
              </span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  {{ auth.user?.role === 'admin' ? '管理员' : '普通用户' }}
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  登出
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="layout-main">
        <RouterView />
      </el-main>
    </el-container>

    <!-- 移动端抽屉 (仅 mobile 渲染) -->
    <el-drawer
      v-if="isMobile"
      v-model="drawerVisible"
      direction="ltr"
      size="240px"
      :with-header="false"
      class="mobile-drawer"
    >
      <div class="drawer-inner">
        <div class="brand brand-drawer">
          <el-icon :size="22"><Connection /></el-icon>
          <span class="brand-name">Media Manager</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          :router="false"
          background-color="#1f2937"
          text-color="#cbd5e1"
          active-text-color="#60a5fa"
          @select="handleSelect"
        >
          <el-menu-item v-for="n in navItems" :key="n.path" :index="n.path">
            <el-icon><component :is="n.icon" /></el-icon>
            <template #title>{{ n.label }}</template>
          </el-menu-item>
        </el-menu>
      </div>
    </el-drawer>
  </el-container>
</template>

<style scoped>
.layout-root {
  height: 100vh;
}
.layout-aside {
  background: #1f2937;
  transition: width 0.2s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.layout-aside :deep(.el-menu) {
  flex: 1;
  overflow-y: auto;
}
.aside-collapse {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  border-top: 1px solid #334155;
  color: #94a3b8;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
  flex-shrink: 0;
}
.aside-collapse:hover {
  background: #334155;
  color: #f1f5f9;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  color: #f1f5f9;
  border-bottom: 1px solid #334155;
}
.brand-name {
  font-weight: 600;
  font-size: 16px;
}
.layout-header {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  height: 56px;
  padding: 0 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0; /* 让 page-title 可截断 */
  flex-shrink: 0;
}
.mobile-menu-btn {
  padding: 4px 6px;
}
.global-search {
  flex: 1;
  max-width: 480px;
  min-width: 0;
}
.search-suggest {
  padding: 4px 0;
}
.s-title {
  font-size: 13px;
  font-weight: 500;
}
.s-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #6b7280;
}
.muted {
  color: #9ca3af;
}
.page-title {
  font-size: 16px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}
.user-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: #374151;
  max-width: 140px;
}
.user-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-trigger:hover {
  background: #f3f4f6;
}
.health-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.health-dot.ok {
  background: #10b981;
}
.health-dot.bad {
  background: #ef4444;
}
.layout-main {
  background: #f5f7fa;
  padding: 16px;
}

/* 移动端 layout-main 缩小 padding,让卡片有更多空间 */
@media (max-width: 768px) {
  .layout-main {
    padding: 8px;
  }
  .global-search {
    max-width: none;
  }
  .page-title {
    font-size: 14px;
  }
  .user-trigger {
    max-width: 80px;
    padding: 4px 6px;
  }
}

:deep(.el-menu) {
  border-right: none;
}

/* 抽屉里的菜单去掉默认白底 */
.drawer-inner {
  background: #1f2937;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.brand-drawer {
  border-bottom: 1px solid #334155;
}
</style>

<style>
/* 抽屉容器去掉内边距 */
.mobile-drawer .el-drawer__body {
  padding: 0 !important;
  background: #1f2937;
}
</style>
