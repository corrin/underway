<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<template>
  <div class="app">
    <header v-if="authStore.isAuthenticated()">
      <nav>
        <div class="nav-left">
          <RouterLink to="/" class="brand">Underway</RouterLink>
          <RouterLink to="/">Home</RouterLink>
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
  border-bottom: 1px solid var(--color-border);
  background: var(--color-background-soft);
}

nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 960px;
  margin: 0 auto;
  padding: 0.75rem 1rem;
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
  color: var(--color-text);
}

nav a {
  text-decoration: none;
  color: var(--color-text-muted, #888);
  font-size: 0.9rem;
}

nav a.router-link-exact-active {
  color: var(--color-text);
}

.logout-btn {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 0.35rem 0.75rem;
  color: var(--color-text-muted, #888);
  cursor: pointer;
  font-size: 0.85rem;
}

.logout-btn:hover {
  color: var(--color-text);
  border-color: var(--color-text);
}
</style>
