<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api/client'

interface Settings {
  ai_api_key: string | null
  ai_api_base: string | null
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

const route = useRoute()
const settings = ref<Settings>({
  ai_api_key: null,
  ai_api_base: null,
  ai_instructions: null,
  llm_model: null,
  schedule_slot_duration: 60,
})

const accounts = ref<ExternalAccount[]>([])
const saving = ref(false)
const saved = ref(false)
const error = ref<string | null>(null)
const oauthStatus = ref<'success' | 'error' | null>(null)
const oauthProvider = ref<string | null>(null)

interface ModelTestResult {
  model: string
  api_base: string | null
  api_key_hint: string
  completion: boolean
  completion_error: string | null
  streaming: boolean
  streaming_error: string | null
  tool_calling: boolean
  tool_calling_error: string | null
}

const testResult = ref<ModelTestResult | null>(null)
const testing = ref(false)
const connecting = ref<'google' | 'o365' | null>(null)

async function loadSettings() {
  try {
    const response = await api.get('/settings')
    // Merge into existing object so fields added in new backend versions
    // (e.g. ai_api_base) are always present even if the old response omitted them.
    Object.assign(settings.value, response.data)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load settings'
  }
}

async function loadAccounts() {
  try {
    const response = await api.get('/external-accounts')
    accounts.value = response.data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load accounts'
  }
}

async function saveSettings() {
  saving.value = true
  saved.value = false
  error.value = null
  try {
    await api.put('/settings', {
      ai_api_key: settings.value.ai_api_key ?? null,
      ai_api_base: settings.value.ai_api_base ?? null,
      ai_instructions: settings.value.ai_instructions ?? null,
      llm_model: settings.value.llm_model ?? null,
      schedule_slot_duration: settings.value.schedule_slot_duration ?? null,
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to save settings'
  } finally {
    saving.value = false
  }
}

async function testModel() {
  testing.value = true
  testResult.value = null
  error.value = null
  try {
    const response = await api.post('/settings/test-model')
    testResult.value = response.data
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Test failed'
  } finally {
    testing.value = false
  }
}

async function connectGoogle() {
  if (connecting.value) return
  error.value = null
  connecting.value = 'google'
  try {
    const response = await api.post('/oauth/google/initiate')
    window.location.href = response.data.authorization_url
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to initiate Google connection'
    connecting.value = null
  }
}

async function connectO365() {
  if (connecting.value) return
  error.value = null
  connecting.value = 'o365'
  try {
    const response = await api.post('/oauth/o365/initiate')
    window.location.href = response.data.authorization_url
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to initiate O365 connection'
    connecting.value = null
  }
}

onMounted(() => {
  const oauth = route.query.oauth as string | undefined
  const provider = route.query.provider as string | undefined
  if (oauth === 'success') {
    oauthStatus.value = 'success'
    oauthProvider.value = provider ?? null
  } else if (oauth === 'error') {
    oauthStatus.value = 'error'
  }
  loadSettings()
  loadAccounts()
})
</script>

<template>
  <div class="settings-page">
    <h1>Settings</h1>

    <div v-if="oauthStatus === 'success'" class="banner banner--success">
      ✓ {{ oauthProvider ? oauthProvider.toUpperCase() : 'Account' }} connected successfully.
    </div>
    <div v-if="oauthStatus === 'error'" class="banner banner--error">
      ✗ OAuth connection failed. Please try again.
    </div>
    <div v-if="error" class="banner banner--error">{{ error }}</div>

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
        <label for="ai_api_base">API Base URL <span class="field-hint">(optional — e.g. https://api.moonshot.cn/v1)</span></label>
        <input id="ai_api_base" v-model="settings.ai_api_base" type="text" placeholder="Leave blank to use provider default" />
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

      <div class="form-actions">
        <button type="submit" :disabled="saving">
          {{ saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save Settings' }}
        </button>
        <button type="button" class="btn-test" :disabled="testing" @click="testModel">
          {{ testing ? 'Testing...' : 'Test Model' }}
        </button>
      </div>
    </form>

    <div v-if="testResult" class="test-results">
      <h3>Test results — <code>{{ testResult.model }}</code></h3>
      <div class="test-meta">
        <span>Key stored: <code>{{ testResult.api_key_hint }}</code></span>
        <span>Base URL: <code>{{ testResult.api_base || '(provider default)' }}</code></span>
      </div>
      <ul class="test-list">
        <li :class="testResult.completion ? 'pass' : 'fail'">
          <span class="test-icon">{{ testResult.completion ? '✓' : '✗' }}</span>
          <span class="test-label">Basic completion</span>
          <span v-if="testResult.completion_error" class="test-error">{{ testResult.completion_error }}</span>
        </li>
        <li :class="testResult.streaming ? 'pass' : 'fail'">
          <span class="test-icon">{{ testResult.streaming ? '✓' : '✗' }}</span>
          <span class="test-label">Streaming</span>
          <span v-if="testResult.streaming_error" class="test-error">{{ testResult.streaming_error }}</span>
        </li>
        <li :class="testResult.tool_calling ? 'pass' : 'fail'">
          <span class="test-icon">{{ testResult.tool_calling ? '✓' : '✗' }}</span>
          <span class="test-label">Tool calling</span>
          <span v-if="testResult.tool_calling_error" class="test-error">{{ testResult.tool_calling_error }}</span>
        </li>
      </ul>
    </div>

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

      <div class="connect-buttons">
        <button class="btn-connect" :disabled="!!connecting" @click="connectGoogle">
          {{ connecting === 'google' ? 'Connecting…' : 'Connect Google Calendar' }}
        </button>
        <button class="btn-connect" :disabled="!!connecting" @click="connectO365">
          {{ connecting === 'o365' ? 'Connecting…' : 'Connect Microsoft 365' }}
        </button>
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

.field-hint {
  font-weight: 400;
  font-size: 0.8rem;
  opacity: 0.6;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.btn-test {
  padding: 0.7rem 1.5rem;
  background: transparent;
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}

.btn-test:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-results {
  margin-bottom: 2rem;
  padding: 1rem 1.25rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-background-soft);
}

.test-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.8rem;
  opacity: 0.7;
  margin-bottom: 0.75rem;
}

.test-results h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.test-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.test-list li {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.9rem;
  padding: 0.3rem 0;
}

.test-icon {
  font-weight: 700;
  width: 1rem;
}

.pass .test-icon { color: #16a34a; }
.fail .test-icon { color: #dc2626; }

.test-label {
  min-width: 130px;
}

.test-error {
  font-size: 0.8rem;
  color: #dc2626;
  opacity: 0.85;
}

.banner {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
}

.banner--success {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #86efac;
}

.banner--error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

.connect-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.25rem;
  flex-wrap: wrap;
}

.btn-connect {
  padding: 0.6rem 1.2rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.9rem;
  cursor: pointer;
  font-weight: 500;
}

.btn-connect:hover {
  background: var(--color-background-soft);
}
</style>
