<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer,
  FolderOpened,
  Search,
  Download,
  Setting,
  Connection,
  ArrowDown,
  SwitchButton,
  CopyDocument,
} from '@element-plus/icons-vue'
import { systemApi, type AppInfo } from '@/api/system'
import { setAuthFailureHandler } from '@/api/http'
import { useAuthStore } from '@/store/auth'
import { searchApi, type LocalSearchHit } from '@/api/search'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapse = ref(false)
const info = ref<AppInfo | null>(null)
const healthy = ref<boolean | null>(null)

// 全局搜索
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
  { path: '/duplicates', label: '重复检测', icon: CopyDocument },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/downloads', label: '下载', icon: Download },
  { path: '/settings', label: '设置', icon: Setting },
]

const handleSelect = (path: string) => router.push(path)

const handleUserCmd = async (cmd: string) => {
  if (cmd === 'logout') {
    await auth.logout()
    router.replace('/login')
  }
}

onMounted(async () => {
  // 注册 401 处理
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
    <el-aside :width="collapse ? '64px' : '220px'" class="layout-aside">
      <div class="brand">
        <el-icon :size="22"><Connection /></el-icon>
        <span v-if="!collapse" class="brand-name">MediaHub</span>
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
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <el-button text @click="collapse = !collapse">
            <span class="toggle">{{ collapse ? '»' : '«' }}</span>
          </el-button>
          <span class="page-title">{{ route.meta.title }}</span>
        </div>

        <el-autocomplete
          v-model="globalQ"
          :fetch-suggestions="onGlobalQuery"
          placeholder="快速搜索本地资源…"
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
          <el-tag v-if="healthy === true" type="success" size="small">后端在线</el-tag>
          <el-tag v-else-if="healthy === false" type="danger" size="small">后端离线</el-tag>
          <el-tag v-if="info?.qbittorrent_configured" type="info" size="small">qB</el-tag>
          <el-tag v-if="info?.jellyfin_configured" type="info" size="small">Jellyfin</el-tag>

          <el-dropdown trigger="click" @command="handleUserCmd">
            <span class="user-trigger">
              {{ auth.user?.display_name || auth.user?.username || '...' }}
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
  gap: 16px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  height: 56px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}
.global-search {
  flex: 1;
  max-width: 480px;
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
.toggle {
  font-size: 16px;
  color: #6b7280;
}
.page-title {
  font-size: 16px;
  font-weight: 500;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.user-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  color: #374151;
}
.user-trigger:hover {
  background: #f3f4f6;
}
.layout-main {
  background: #f5f7fa;
  padding: 16px;
}

:deep(.el-menu) {
  border-right: none;
}
</style>
