<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const submit = async () => {
  if (!formRef.value) return
  await formRef.value.validate().catch(() => null)
  if (!form.username || !form.password) return

  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success(`欢迎回来,${auth.user?.display_name || auth.user?.username}`)
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    ElMessage.error(detail === 'invalid_credentials' ? '用户名或密码错误' : detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="card">
      <div class="brand">
        <el-icon :size="32" color="#3b82f6"><Connection /></el-icon>
        <h1 class="title">Media Manager</h1>
        <div class="subtitle">NAS 资源库与视频管理系统</div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit" @click="submit">
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
}
.card {
  width: 380px;
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
.title {
  margin: 8px 0 4px;
  font-size: 22px;
}
.subtitle {
  color: #6b7280;
  font-size: 13px;
}
.submit {
  width: 100%;
}
</style>
