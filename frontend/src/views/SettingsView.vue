<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api/client'
import { useTheme } from '@/composables/useTheme'

const { theme, setTheme } = useTheme()

interface Settings {
  ai_api_key: string | null
  ai_instructions: string | null
  llm_model: string | null
  schedule_slot_duration: number | null
}

interface ExternalAccount {
  id: string
  external_email: string
  provider: string
  is_primary_calendar: boolean
  is_primary_tasks: boolean
  use_for_calendar: boolean
  use_for_tasks: boolean
  needs_reauth: boolean
  last_sync: string | null
}

const settings = ref<Settings>({
  ai_api_key: null,
  ai_instructions: null,
  llm_model: null,
  schedule_slot_duration: 60,
})

const accounts = ref<ExternalAccount[]>([])
const saving = ref(false)
const saved = ref(false)

async function loadSettings() {
  const response = await api.get('/settings')
  settings.value = response.data
}

async function loadAccounts() {
  const response = await api.get('/external-accounts')
  accounts.value = response.data
}

async function saveSettings() {
  saving.value = true
  saved.value = false
  await api.put('/settings', settings.value)
  saving.value = false
  saved.value = true
  setTimeout(() => {
    saved.value = false
  }, 2000)
}

onMounted(() => {
  loadSettings()
  loadAccounts()
})
</script>

<template>
  <div class="settings-page">
    <h1>Settings</h1>

    <section class="appearance-section">
      <h2>Appearance</h2>
      <div class="theme-options">
        <label class="theme-option">
          <input type="radio" name="theme" value="light" :checked="theme === 'light'" @change="setTheme('light')" />
          Light
        </label>
        <label class="theme-option">
          <input type="radio" name="theme" value="dark" :checked="theme === 'dark'" @change="setTheme('dark')" />
          Dark
        </label>
        <label class="theme-option">
          <input type="radio" name="theme" value="auto" :checked="theme === 'auto'" @change="setTheme('auto')" />
          Auto (system default)
        </label>
      </div>
    </section>

    <form class="settings-form" @submit.prevent="saveSettings">
      <div class="field">
        <label for="llm_model">AI Model</label>
        <input id="llm_model" v-model="settings.llm_model" type="text" placeholder="e.g. claude-sonnet-4-20250514" />
      </div>

      <div class="field">
        <label for="ai_api_key">API Key</label>
        <input id="ai_api_key" v-model="settings.ai_api_key" type="password" placeholder="Your AI provider API key" />
      </div>

      <div class="field">
        <label for="ai_instructions">AI Instructions</label>
        <textarea
          id="ai_instructions"
          v-model="settings.ai_instructions"
          rows="4"
          placeholder="Custom instructions for the AI assistant"
        ></textarea>
      </div>

      <div class="field">
        <label for="schedule_slot_duration">Schedule Slot Duration</label>
        <select id="schedule_slot_duration" v-model.number="settings.schedule_slot_duration">
          <option :value="30">30 minutes</option>
          <option :value="60">60 minutes</option>
          <option :value="120">120 minutes</option>
        </select>
      </div>

      <button type="submit" :disabled="saving">
        {{ saving ? 'Saving...' : saved ? 'Saved' : 'Save Settings' }}
      </button>
    </form>

    <section class="accounts-section">
      <h2>External Accounts</h2>
      <div v-if="accounts.length === 0" class="empty">No external accounts connected.</div>
      <div v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-info">
          <strong>{{ account.provider }}</strong>
          <span>{{ account.external_email }}</span>
        </div>
        <div class="account-status">
          <span v-if="account.needs_reauth" class="badge warning">Needs re-auth</span>
          <span v-if="account.use_for_calendar" class="badge">Calendar</span>
          <span v-if="account.use_for_tasks" class="badge">Tasks</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

h1 {
  margin-bottom: 1.5rem;
}

.appearance-section {
  margin-bottom: 2rem;
}

.theme-options {
  display: flex;
  gap: 1.5rem;
  margin-top: 0.5rem;
}

.theme-option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  font-size: 0.95rem;
}

h2 {
  margin-bottom: 1rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-bottom: 3rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-weight: 600;
  font-size: 0.9rem;
}

.field input,
.field textarea,
.field select {
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.95rem;
}

button[type='submit'] {
  padding: 0.7rem 1.5rem;
  background: var(--color-text);
  color: var(--color-background);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  align-self: flex-start;
}

button[type='submit']:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.accounts-section {
  border-top: 1px solid var(--color-border);
  padding-top: 2rem;
}

.empty {
  color: var(--color-text-muted, #888);
  font-style: italic;
}

.account-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  margin-bottom: 0.5rem;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.account-info span {
  font-size: 0.85rem;
  color: var(--color-text-muted, #888);
}

.account-status {
  display: flex;
  gap: 0.4rem;
}

.badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
}

.badge.warning {
  background: #fef3c7;
  color: #92400e;
  border-color: #f59e0b;
}
</style>
