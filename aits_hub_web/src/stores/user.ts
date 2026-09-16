import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getCurrentUser } from '@/api/auth'

export interface UserInfo {
  id: number
  username: string
  email: string
  full_name: string
  is_admin: boolean
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await loginApi(username, password)
    token.value = res.access_token
    userInfo.value = res.user
    localStorage.setItem('token', res.access_token)
    return res
  }

  async function fetchUserInfo() {
    if (!token.value) return null
    try {
      const res = await getCurrentUser()
      userInfo.value = res
      return res
    } catch {
      logout()
      return null
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, isLoggedIn, login, fetchUserInfo, logout }
})
