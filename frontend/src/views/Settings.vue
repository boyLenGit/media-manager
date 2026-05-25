<script setup lang="ts">
import { ref } from 'vue'
import ScanPathsTab from './settings/ScanPathsTab.vue'
import UsersTab from './settings/UsersTab.vue'
import PlaybackTargetsTab from './settings/PlaybackTargetsTab.vue'
import SmbConfigTab from './settings/SmbConfigTab.vue'
import AuthorsTab from './settings/AuthorsTab.vue'
import MediaTypesTab from './settings/MediaTypesTab.vue'
import TagsTab from './settings/TagsTab.vue'
import DownloaderTab from './settings/DownloaderTab.vue'
import SearchSourcesTab from './settings/SearchSourcesTab.vue'
import JellyfinTab from './settings/JellyfinTab.vue'
import ParsersTab from './settings/ParsersTab.vue'

const active = ref('paths')
</script>

<template>
  <div class="settings">
    <el-card>
      <el-tabs v-model="active" tab-position="left">
        <el-tab-pane label="扫描路径" name="paths">
          <ScanPathsTab v-if="active === 'paths'" />
        </el-tab-pane>
        <el-tab-pane label="解析器" name="parsers">
          <ParsersTab v-if="active === 'parsers'" />
        </el-tab-pane>
        <el-tab-pane label="资源类型" name="types">
          <MediaTypesTab v-if="active === 'types'" />
        </el-tab-pane>
        <el-tab-pane label="作者" name="authors">
          <AuthorsTab v-if="active === 'authors'" />
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
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.settings {
  height: 100%;
}
:deep(.el-tabs__content) {
  padding-left: 16px;
}
</style>
