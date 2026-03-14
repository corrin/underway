<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

onMounted(() => {
  const token = route.query.token as string | undefined
  const email = route.query.user_email as string | undefined
  const userId = route.query.user_id as string | undefined

  if (token && email && userId) {
    authStore.setSession(token, { id: userId, email, llm_model: null, ai_instructions: null, schedule_slot_duration: null })
    router.replace('/')
  } else {
    router.replace('/login')
  }
})
</script>

<template>
  <div class="callback-page">
    <p data-automation-id="auth-callback-status">Signing in...</p>
  </div>
</template>
