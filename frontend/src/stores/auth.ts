import { ref } from 'vue'
import { defineStore } from 'pinia'
import api from '@/api/client'

export interface User {
  id: string
  email: string
  llm_model: string | null
  ai_instructions: string | null
  schedule_slot_duration: number | null
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  async function login(idToken: string): Promise<void> {
    const response = await api.post('/auth/google', { id_token: idToken })
    token.value = response.data.token
    user.value = response.data.user
    localStorage.setItem('token', response.data.token)
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return
    const response = await api.get('/auth/me')
    user.value = response.data
  }

  function logout(): void {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  const isAuthenticated = () => !!token.value

  return { user, token, login, fetchUser, logout, isAuthenticated }
})
