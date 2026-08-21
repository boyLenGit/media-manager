<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import ScanPathsTab from './settings/ScanPathsTab.vue'
import UsersTab from './settings/UsersTab.vue'
import PlaybackTargetsTab from './settings/PlaybackTargetsTab.vue'
import SmbConfigTab from './settings/SmbConfigTab.vue'
import MediaTypesTab from './settings/MediaTypesTab.vue'
import TagsTab from './settings/TagsTab.vue'
import DownloaderTab from './settings/DownloaderTab.vue'
import SearchSourcesTab from './settings/SearchSourcesTab.vue'
import JellyfinTab from './settings/JellyfinTab.vue'
import ParsersTab from './settings/ParsersTab.vue'
import DangerZoneTab from './settings/DangerZoneTab.vue'
import AuditLogTab from './settings/AuditLogTab.vue'

const active = ref('paths')

// 移动端: tab 顶部水平排列(left 模式 768px 下会被严重挤压)
const MOBILE_BREAKPOINT = 768
const isMobile = ref(window.innerWidth < MOBILE_BREAKPOINT)
const onResize = () => (isMobile.value = window.innerWidth < MOBILE_BREAKPOINT)
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

const tabPosition = computed(() => (isMobile.value ? 'top' : 'left'))
</script>

<template>
  <div class="settings">
    <el-card body-style="padding: 0">
      <el-tabs v-model="active" :tab-position="tabPosition" class="settings-tabs">
        <el-tab-pane label="扫描路径" name="paths">
          <ScanPathsTab v-if="active === 'paths'" />
        </el-tab-pane>
        <el-tab-pane label="解析器" name="parsers">
          <ParsersTab v-if="active === 'parsers'" />
        </el-tab-pane>
        <el-tab-pane label="资源类型" name="types">
          <MediaTypesTab v-if="active === 'types'" />
        </el-tab-pane>
        <el-tab-pane label="标签" name="tags">
          <TagsTab v-if="active === 'tags'" />
        </el-tab-pane>
        <el-tab-pane label="播放目标" name="targets">
          <PlaybackTargetsTab v-if="active === 'targets'" />
        </el-tab-pane>
        <el-tab-pane label="SMB 配置" name="smb">
          <SmbConfigTab v-if="active === 'smb'" />
        </el-tab-pane>
        <el-tab-pane label="下载器" name="downloader">
          <DownloaderTab v-if="active === 'downloader'" />
        </el-tab-pane>
        <el-tab-pane label="搜索源" name="sources">
          <SearchSourcesTab v-if="active === 'sources'" />
        </el-tab-pane>
        <el-tab-pane label="Jellyfin" name="jellyfin">
          <JellyfinTab v-if="active === 'jellyfin'" />
        </el-tab-pane>
        <el-tab-pane label="用户管理" name="users">
          <UsersTab v-if="active === 'users'" />
        </el-tab-pane>
        <el-tab-pane label="审计日志" name="audit">
          <AuditLogTab v-if="active === 'audit'" />
        </el-tab-pane>
        <el-tab-pane name="danger">
          <template #label>
            <span style="color: #dc2626">危险区</span>
          </template>
          <DangerZoneTab v-if="active === 'danger'" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.settings {
  height: 100%;
}
.settings-tabs {
  padding: 12px;
}
:deep(.el-tabs__content) {
  padding-left: 16px;
}

/* 移动端: tabs 顶部水平滚动,内容左 padding 取消 */
@media (max-width: 768px) {
  .settings-tabs {
    padding: 8px;
  }
  :deep(.el-tabs--top .el-tabs__nav-wrap) {
    overflow-x: auto;
  }
  :deep(.el-tabs--top .el-tabs__nav) {
    white-space: nowrap;
  }
  :deep(.el-tabs__content) {
    padding-left: 0;
  }
}
</style>
