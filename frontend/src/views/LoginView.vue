<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink } from 'vue-router'

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
      ux_mode: 'redirect',
      login_uri: window.location.origin + '/api/auth/google/callback',
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
      <h1>Welcome to Underway</h1>

      <p>This app allows you to turn your todo list into meetings, using AI to help keep you on track.</p>

      <p>If you want to use the app, you'll need to log in with any Google account.</p>

      <h3>How it works</h3>
      <p>Once you're signed into your Google account, you can add as many calendar accounts (like Google Calendar) and task accounts (e.g., Todoist) as you like. The app will intelligently break your tasks down into 30 or 60 minute chunks and schedule them according to any guidelines you provide. You need to tell the app when you finish a task, or it will keep trying to schedule it.</p>

      <h3>Pricing</h3>
      <p>Anybody with a Google account can currently use the app for free. No credit card or billing info is collected at this time. When we start charging, we will contact all users well in advance to ask them to add billing information if they wish to continue.</p>

      <h3>Our Approach to Task Management</h3>
      <p>We find this approach works much better than deadlines for a bunch of reasons. Two of the main ones are:</p>
      <ul>
        <li>If you start missing deadlines due to something urgent coming up, traditional to-do managers often struggle to reprioritize, simply marking everything as overdue.</li>
        <li>Most deadlines are pretty arbitrary. We believe Kanban-style priorities, focusing on what's next, work better for most people's workflows.</li>
      </ul>

      <div id="g_id_signin" class="google-btn"></div>

      <div class="footer-links">
        <RouterLink to="/about">About</RouterLink>
        <span class="separator">|</span>
        <RouterLink to="/privacy">Privacy</RouterLink>
        <span class="separator">|</span>
        <RouterLink to="/terms">Terms</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  min-height: 100vh;
  padding: 3rem 1.5rem;
}

.login-card {
  padding: 2.5rem;
  border-radius: 12px;
  background: var(--color-background-soft);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  max-width: 640px;
  width: 100%;
}

.login-card h1 {
  font-size: 2rem;
  margin-bottom: 1.5rem;
  text-align: center;
}

.login-card h3 {
  margin-top: 1.5rem;
  margin-bottom: 0.5rem;
}

.login-card p {
  margin-bottom: 1rem;
  line-height: 1.6;
}

.login-card ul {
  padding-left: 1.5rem;
  margin-bottom: 1rem;
}

.login-card ul li {
  margin-bottom: 0.5rem;
  line-height: 1.6;
}

.google-btn {
  display: flex;
  justify-content: center;
  margin-top: 2rem;
}

.footer-links {
  margin-top: 2rem;
  font-size: 0.85rem;
  text-align: center;
  color: var(--color-text-muted, #888);
}

.footer-links a {
  color: var(--color-text-muted, #888);
  text-decoration: none;
}

.footer-links a:hover {
  text-decoration: underline;
}

.footer-links .separator {
  margin: 0 0.5rem;
}
</style>
