<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <div class="login-logo">
          <BugOutlined :style="{ fontSize: '32px', color: '#1677ff' }" />
        </div>
        <h2>AITS 智能测试管理平台</h2>
        <p>LangChain + Agent 驱动的下一代测试平台</p>
      </div>

      <a-tabs v-model:activeKey="activeTab" class="login-tabs" centered>
        <a-tab-pane key="login" tab="登录">
          <a-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            layout="vertical"
            @finish="handleLogin"
          >
            <a-form-item name="username">
              <a-input
                v-model:value="loginForm.username"
                size="large"
                placeholder="用户名"
              >
                <template #prefix>
                  <UserOutlined />
                </template>
              </a-input>
            </a-form-item>
            <a-form-item name="password">
              <a-input-password
                v-model:value="loginForm.password"
                size="large"
                placeholder="密码"
              >
                <template #prefix>
                  <LockOutlined />
                </template>
              </a-input-password>
            </a-form-item>
            <a-form-item>
              <a-button
                type="primary"
                size="large"
                html-type="submit"
                :loading="loading"
                block
              >
                登录
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>

        <a-tab-pane key="register" tab="注册">
          <a-form
            ref="registerFormRef"
            :model="registerForm"
            :rules="registerRules"
            layout="vertical"
            @finish="handleRegister"
          >
            <a-form-item name="username">
              <a-input
                v-model:value="registerForm.username"
                size="large"
                placeholder="用户名"
              >
                <template #prefix>
                  <UserOutlined />
                </template>
              </a-input>
            </a-form-item>
            <a-form-item name="email">
              <a-input
                v-model:value="registerForm.email"
                size="large"
                placeholder="邮箱"
              >
                <template #prefix>
                  <MailOutlined />
                </template>
              </a-input>
            </a-form-item>
            <a-form-item name="password">
              <a-input-password
                v-model:value="registerForm.password"
                size="large"
                placeholder="密码"
              >
                <template #prefix>
                  <LockOutlined />
                </template>
              </a-input-password>
            </a-form-item>
            <a-form-item name="full_name">
              <a-input
                v-model:value="registerForm.full_name"
                size="large"
                placeholder="姓名（可选）"
              >
                <template #prefix>
                  <IdcardOutlined />
                </template>
              </a-input>
            </a-form-item>
            <a-form-item>
              <a-button
                type="primary"
                size="large"
                html-type="submit"
                :loading="loading"
                block
              >
                注册
              </a-button>
            </a-form-item>
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, MailOutlined, IdcardOutlined, BugOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'
import { useUserStore } from '@/stores/user'
import { register as registerApi } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref<FormInstance>()
const registerFormRef = ref<FormInstance>()

const loginForm = reactive({
  username: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  full_name: ''
})

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const registerRules = {
  username: [{ required: true, min: 3, message: '用户名至少3个字符', trigger: 'blur' }],
  email: [{ required: true, type: 'email', message: '请输入正确的邮箱', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少6个字符', trigger: 'blur' }]
}

async function handleLogin() {
  loading.value = true
  try {
    await userStore.login(loginForm.username, loginForm.password)
    message.success('登录成功')
    router.push('/')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  loading.value = true
  try {
    await registerApi(registerForm)
    message.success('注册成功，请登录')
    activeTab.value = 'login'
    loginForm.username = registerForm.username
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
}

.login-box {
  width: 420px;
  padding: 40px 36px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12),
    0 9px 28px 8px rgba(0, 0, 0, 0.05);
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.login-logo {
  margin-bottom: 16px;
}

.login-header h2 {
  font-size: 22px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
  margin: 0 0 8px 0;
}

.login-header p {
  color: rgba(0, 0, 0, 0.45);
  font-size: 14px;
  margin: 0;
}

.login-tabs {
  margin-top: 8px;
}
</style>
