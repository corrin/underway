<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function handleCredentialResponse(response: { credential: string }) {
  authStore.login(response.credential).then(() => {
    router.push('/')
  })
}

onMounted(() => {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  if (!clientId) {
    console.error('VITE_GOOGLE_CLIENT_ID not set')
    return
  }

  // Load Google Identity Services script
  const script = document.createElement('script')
  script.src = 'https://accounts.google.com/gsi/client'
  script.async = true
  script.onload = () => {
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCredentialResponse,
    })
    window.google.accounts.id.renderButton(document.getElementById('g_id_signin')!, {
      theme: 'outline',
      size: 'large',
      width: 300,
    })
  }
  document.head.appendChild(script)
})
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1>Underway</h1>
      <p>Intelligent task and calendar management</p>
      <div id="g_id_signin" class="google-btn"></div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.login-card {
  text-align: center;
  padding: 3rem 2.5rem;
  border-radius: 12px;
  background: var(--color-background-soft);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  max-width: 400px;
  width: 100%;
}

.login-card h1 {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.login-card p {
  color: var(--color-text-muted, #888);
  margin-bottom: 2rem;
}

.google-btn {
  display: flex;
  justify-content: center;
}
</style>
