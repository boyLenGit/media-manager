<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { authApi } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const checking = ref(true)

const form = reactive({
  username: '',
  password: '',
  password_confirm: '',
  display_name: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名 3-64 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
  password_confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_, value, cb) => {
        if (value !== form.password) cb(new Error('两次密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

onMounted(async () => {
  try {
    const { setup_required } = await authApi.setupRequired()
    if (!setup_required) {
      router.replace('/login')
      return
    }
  } catch {
    /* 默认允许进入 */
  }
  checking.value = false
})

const submit = async () => {
  if (!formRef.value) return
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  loading.value = true
  try {
    await auth.setup({
      username: form.username,
      password: form.password,
      display_name: form.display_name || undefined,
    })
    ElMessage.success('管理员账号创建成功')
    router.replace('/')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '初始化失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="setup-page">
    <el-card class="card" v-loading="checking">
      <div class="brand">
        <el-icon :size="32" color="#3b82f6"><Connection /></el-icon>
        <h1 class="title">欢迎使用 Media Manager</h1>
        <div class="subtitle">首次启动,请创建管理员账号</div>
      </div>

      <el-form
        v-if="!checking"
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="显示名(可选)">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="password_confirm">
          <el-input
            v-model="form.password_confirm"
            type="password"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit" @click="submit">
          创建管理员
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.setup-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
}
.card {
  width: 420px;
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
