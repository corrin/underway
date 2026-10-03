import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear the store too, not just localStorage — otherwise the router guard
      // still sees an authenticated user and bounces /login back to /chat.
      useAuthStore().logout()
    }
    return Promise.reject(error)
  },
)

export default api
