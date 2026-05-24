<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { authApi, type UserInfo } from '@/api/auth'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const users = ref<UserInfo[]>([])
const loading = ref(false)

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editing = ref<UserInfo | null>(null)
const form = reactive({
  username: '',
  password: '',
  display_name: '',
  role: 'viewer' as 'admin' | 'viewer',
  enabled: true,
})

const fetchUsers = async () => {
  loading.value = true
  try {
    users.value = await authApi.listUsers()
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  dialogMode.value = 'create'
  editing.value = null
  Object.assign(form, {
    username: '',
    password: '',
    display_name: '',
    role: 'viewer',
    enabled: true,
  })
  dialogVisible.value = true
}

const openEdit = (u: UserInfo) => {
  dialogMode.value = 'edit'
  editing.value = u
  Object.assign(form, {
    username: u.username,
    password: '',
    display_name: u.display_name || '',
    role: u.role,
    enabled: u.enabled,
  })
  dialogVisible.value = true
}

const save = async () => {
  try {
    if (dialogMode.value === 'create') {
      if (!form.username || !form.password) {
        ElMessage.warning('请填写用户名和密码')
        return
      }
      await authApi.createUser({
        username: form.username,
        password: form.password,
        display_name: form.display_name || undefined,
        role: form.role,
      })
      ElMessage.success('已创建')
    } else if (editing.value) {
      const payload: any = {
        display_name: form.display_name || undefined,
        role: form.role,
        enabled: form.enabled,
      }
      if (form.password) payload.password = form.password
      await authApi.updateUser(editing.value.id, payload)
      ElMessage.success('已更新')
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'username_taken') ElMessage.error('用户名已存在')
  }
}

const remove = async (u: UserInfo) => {
  await ElMessageBox.confirm(`删除用户「${u.username}」?此操作不可恢复。`, '确认', {
    type: 'warning',
  }).catch(() => null)
  try {
    await authApi.deleteUser(u.id)
    ElMessage.success('已删除')
    await fetchUsers()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'cannot_delete_self')
      ElMessage.error('不能删除当前登录用户')
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div class="users">
    <div class="header">
      <h3 class="section-title">用户管理</h3>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加用户</el-button>
    </div>

    <el-alert
      v-if="!auth.isAdmin"
      type="warning"
      :closable="false"
      title="只有管理员才能管理用户"
      style="margin-bottom: 12px"
    />

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="显示名" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            type="danger"
            :icon="Delete"
            :disabled="row.id === auth.user?.id"
            @click="remove(row)"
          />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '添加用户' : '编辑用户'"
      width="500px"
    >
      <el-form label-width="100px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" :disabled="dialogMode === 'edit'" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item :label="dialogMode === 'edit' ? '修改密码' : '密码'">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="dialogMode === 'edit' ? '留空表示不修改' : '请输入密码'"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="admin">管理员</el-radio>
            <el-radio value="viewer">普通用户</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="dialogMode === 'edit'" label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.users {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
</style>
