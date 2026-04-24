<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'

const authStore = useAuthStore()
useTheme()
</script>

<template>
  <div class="app">
    <header v-if="authStore.isAuthenticated()">
      <nav>
        <div class="nav-left">
          <RouterLink to="/" class="brand">Underway</RouterLink>
          <RouterLink to="/chat">Chat</RouterLink>
          <RouterLink to="/tasks">Tasks</RouterLink>
        </div>
        <div class="nav-right">
          <RouterLink to="/settings">Settings</RouterLink>
          <button class="logout-btn" @click="authStore.logout()">Logout</button>
        </div>
      </nav>
    </header>

    <RouterView />
  </div>
</template>

<style scoped>
header {
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: #343a40;
}

nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.5rem;
}

.nav-left,
.nav-right {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.brand {
  font-weight: 700;
  font-size: 1.1rem;
  text-decoration: none;
  color: #fff;
}

nav a {
  text-decoration: none;
  color: rgba(255, 255, 255, 0.55);
  font-size: 0.9rem;
}

nav a:hover {
  color: rgba(255, 255, 255, 0.75);
}

nav a.router-link-exact-active {
  color: #fff;
}

.logout-btn {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  color: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  font-size: 0.85rem;
}

.logout-btn:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.75);
}
</style>
