<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api/client'
import { useTheme } from '@/composables/useTheme'
import {
  initiateGoogleOAuth,
  initiateO365OAuth,
  disconnectAccount,
  updateAccountFlags,
  fetchAccounts,
  type ExternalAccount,
} from '@/api/calendar'
import { initiateTodoistOAuth } from '@/api/todoist'

const { theme, setTheme } = useTheme()
const route = useRoute()
const router = useRouter()

interface Settings {
  ai_api_key: string | null
  ai_instructions: string | null
  llm_model: string | null
  schedule_slot_duration: number | null
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

// OAuth feedback banner
const oauthMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)

// Delete confirmation modal
const showDeleteModal = ref(false)
const deleteTarget = ref<ExternalAccount | null>(null)
const deleting = ref(false)

function accountStatus(account: ExternalAccount): string {
  return account.needs_reauth ? 'Needs Reauth' : 'Active'
}

function statusClass(account: ExternalAccount): string {
  return account.needs_reauth ? 'status-warn' : 'status-ok'
}

function providerLabel(provider: string): string {
  if (provider === 'google') return 'Google'
  if (provider === 'o365') return 'Microsoft 365'
  if (provider === 'todoist') return 'Todoist'
  return provider
}

// Is this a dual-use account (calendar + tasks)?
function isDualUse(account: ExternalAccount): boolean {
  return account.use_for_calendar && account.use_for_tasks
}

async function loadSettings() {
  const response = await api.get('/settings')
  settings.value = response.data
}

async function loadAccounts() {
  accounts.value = await fetchAccounts()
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

// Account flag toggles
async function toggleFlag(account: ExternalAccount, flag: string, value: boolean) {
  const flags: Record<string, boolean> = { [flag]: value }

  // Enforce: unchecking read events also unchecks write events
  if (flag === 'use_for_calendar' && !value) {
    flags['write_calendar'] = false
  }

  // Enforce: unchecking read tasks also unchecks write tasks
  if (flag === 'use_for_tasks' && !value) {
    flags['write_tasks'] = false
  }

  await updateAccountFlags(account.id, flags)
  await loadAccounts()
}

// OAuth connect
async function connectGoogle() {
  const { authorization_url } = await initiateGoogleOAuth()
  window.location.href = authorization_url
}

async function connectO365() {
  const { authorization_url } = await initiateO365OAuth()
  window.location.href = authorization_url
}

async function connectTodoist() {
  const { authorization_url } = await initiateTodoistOAuth()
  window.location.href = authorization_url
}

async function reauthAccount(account: ExternalAccount) {
  if (account.provider === 'google') {
    await connectGoogle()
  } else if (account.provider === 'o365') {
    await connectO365()
  } else if (account.provider === 'todoist') {
    await connectTodoist()
  }
}

// Delete
function confirmDelete(account: ExternalAccount) {
  deleteTarget.value = account
  showDeleteModal.value = true
}

async function executeDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await disconnectAccount(deleteTarget.value.id)
    showDeleteModal.value = false
    deleteTarget.value = null
    await loadAccounts()
  } catch {
    // handled by API interceptor
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadSettings()
  loadAccounts()

  // Check for OAuth callback feedback
  const oauth = route.query.oauth as string | undefined
  if (oauth === 'success') {
    oauthMessage.value = { type: 'success', text: 'Account connected successfully.' }
  } else if (oauth === 'error') {
    const detail = (route.query.detail as string) || 'OAuth authorization failed.'
    oauthMessage.value = { type: 'error', text: detail }
  }
  if (oauth) {
    router.replace({ query: {} })
    setTimeout(() => {
      oauthMessage.value = null
    }, 5000)
  }
})
</script>

<template>
  <div class="settings-page">
    <h1>Settings</h1>

    <!-- OAuth feedback banner -->
    <div v-if="oauthMessage" :class="['oauth-banner', oauthMessage.type]">
      {{ oauthMessage.text }}
    </div>

    <section class="appearance-section">
      <h2>Appearance</h2>
      <div class="theme-options">
        <label class="theme-option">
          <input type="radio" name="theme" value="light" data-automation-id="settings-theme-light" :checked="theme === 'light'" @change="setTheme('light')" />
          Light
        </label>
        <label class="theme-option">
          <input type="radio" name="theme" value="dark" data-automation-id="settings-theme-dark" :checked="theme === 'dark'" @change="setTheme('dark')" />
          Dark
        </label>
        <label class="theme-option">
          <input type="radio" name="theme" value="auto" data-automation-id="settings-theme-auto" :checked="theme === 'auto'" @change="setTheme('auto')" />
          Auto (system default)
        </label>
      </div>
    </section>

    <form class="settings-form" @submit.prevent="saveSettings">
      <div class="field">
        <label for="llm_model">AI Model</label>
        <input id="llm_model" v-model="settings.llm_model" type="text" data-automation-id="settings-llm-model" placeholder="e.g. claude-sonnet-4-20250514" />
      </div>

      <div class="field">
        <label for="ai_api_key">API Key</label>
        <input id="ai_api_key" v-model="settings.ai_api_key" type="password" data-automation-id="settings-api-key" placeholder="Your AI provider API key" />
      </div>

      <div class="field">
        <label for="ai_instructions">AI Instructions</label>
        <textarea
          id="ai_instructions"
          v-model="settings.ai_instructions"
          rows="4"
          data-automation-id="settings-ai-instructions"
          placeholder="Custom instructions for the AI assistant"
        ></textarea>
      </div>

      <div class="field">
        <label for="schedule_slot_duration">Schedule Slot Duration</label>
        <select id="schedule_slot_duration" v-model.number="settings.schedule_slot_duration" data-automation-id="settings-slot-duration">
          <option :value="30">30 minutes</option>
          <option :value="60">60 minutes</option>
          <option :value="120">120 minutes</option>
        </select>
      </div>

      <button type="submit" data-automation-id="settings-save-button" :disabled="saving">
        {{ saving ? 'Saving...' : saved ? 'Saved' : 'Save Settings' }}
      </button>
    </form>

    <!-- External Accounts -->
    <section class="accounts-section">
      <h2>External Accounts</h2>

      <div v-if="accounts.length === 0" class="empty">No external accounts connected.</div>

      <div v-else class="accounts-table-wrap">
        <table class="accounts-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Email</th>
              <th>Read Events</th>
              <th>Write Events</th>
              <th>Read Tasks</th>
              <th>Write Tasks</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="account in accounts" :key="account.id" :data-automation-id="`settings-account-row-${account.id}`">
              <td>{{ providerLabel(account.provider) }}</td>
              <td class="col-email">{{ account.external_email }}</td>
              <td class="col-check">
                <input
                  v-if="account.provider !== 'todoist'"
                  type="checkbox"
                  :data-automation-id="`settings-account-read-events-${account.id}`"
                  :aria-label="`Read events for ${account.external_email}`"
                  :checked="account.use_for_calendar"
                  @change="toggleFlag(account, 'use_for_calendar', !account.use_for_calendar)"
                />
              </td>
              <td class="col-check">
                <input
                  v-if="account.provider !== 'todoist'"
                  type="checkbox"
                  :data-automation-id="`settings-account-write-events-${account.id}`"
                  :aria-label="`Write events for ${account.external_email}`"
                  :checked="account.write_calendar"
                  :disabled="!account.use_for_calendar"
                  @change="toggleFlag(account, 'write_calendar', !account.write_calendar)"
                />
              </td>
              <td class="col-check">
                <input
                  type="checkbox"
                  :data-automation-id="`settings-account-read-tasks-${account.id}`"
                  :aria-label="`Read tasks for ${account.external_email}`"
                  :checked="account.use_for_tasks"
                  @change="toggleFlag(account, 'use_for_tasks', !account.use_for_tasks)"
                />
              </td>
              <td class="col-check">
                <input
                  type="checkbox"
                  :data-automation-id="`settings-account-write-tasks-${account.id}`"
                  :aria-label="`Write tasks for ${account.external_email}`"
                  :checked="account.write_tasks"
                  :disabled="!account.use_for_tasks"
                  @change="toggleFlag(account, 'write_tasks', !account.write_tasks)"
                />
              </td>
              <td>
                <span :class="['status-badge', statusClass(account)]">{{ accountStatus(account) }}</span>
              </td>
              <td class="col-actions">
                <button
                  v-if="account.needs_reauth"
                  class="btn-action"
                  :data-automation-id="`settings-account-reauth-${account.id}`"
                  @click="reauthAccount(account)"
                >
                  Reauth
                </button>
                <button
                  class="btn-action btn-delete"
                  :data-automation-id="`settings-account-delete-${account.id}`"
                  @click="confirmDelete(account)"
                >
                  Delete
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Add New Account -->
      <div class="add-account-section">
        <h3>Add New Account</h3>
        <div class="add-buttons">
          <button class="btn connect-btn google" data-automation-id="settings-connect-google" @click="connectGoogle">
            <svg class="btn-icon" viewBox="0 0 24 24"><path fill="#fff" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#fff" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#fff" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/><path fill="#fff" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Sign in with Google
          </button>
          <button class="btn connect-btn o365" data-automation-id="settings-connect-microsoft" @click="connectO365">
            <svg class="btn-icon" viewBox="0 0 21 21"><rect fill="#f25022" x="0" y="0" width="10" height="10"/><rect fill="#7fba00" x="11" y="0" width="10" height="10"/><rect fill="#00a4ef" x="0" y="11" width="10" height="10"/><rect fill="#ffb900" x="11" y="11" width="10" height="10"/></svg>
            Sign in with Microsoft
          </button>
          <button class="btn connect-btn todoist" data-automation-id="settings-connect-todoist" @click="connectTodoist">
            <svg class="btn-icon" viewBox="0 0 24 24"><path fill="#fff" d="M21 1.5H3c-.8 0-1.5.7-1.5 1.5v18c0 .8.7 1.5 1.5 1.5h18c.8 0 1.5-.7 1.5-1.5V3c0-.8-.7-1.5-1.5-1.5zM7.5 7.5l9 4.5-9 4.5V7.5z"/></svg>
            Connect Todoist
          </button>
        </div>
      </div>
    </section>

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteModal" class="modal-overlay" data-automation-id="settings-delete-modal" @click.self="showDeleteModal = false">
      <div class="modal">
        <h3>Delete Account</h3>
        <p v-if="deleteTarget">
          Are you sure you want to delete the
          <strong>{{ providerLabel(deleteTarget.provider) }}</strong> account
          <strong>{{ deleteTarget.external_email }}</strong>?
        </p>
        <p class="warning-text">This will remove stored credentials and cannot be undone.</p>
        <p v-if="deleteTarget && isDualUse(deleteTarget)" class="warning-text">
          This account is used for both Calendar and Tasks. Deleting it will remove access to both.
        </p>
        <div class="modal-actions">
          <button class="btn btn-secondary" data-automation-id="settings-delete-cancel" @click="showDeleteModal = false">Cancel</button>
          <button class="btn btn-danger" data-automation-id="settings-delete-confirm" :disabled="deleting" @click="executeDelete">
            {{ deleting ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

h1 {
  margin-bottom: 1.5rem;
}

h2 {
  margin-bottom: 1rem;
}

h3 {
  margin-bottom: 0.75rem;
}

/* OAuth banner */
.oauth-banner {
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
  font-weight: 500;
}

.oauth-banner.success {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #6ee7b7;
}

.oauth-banner.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

/* Appearance */
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

/* Settings form */
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

/* Accounts section */
.accounts-section {
  border-top: 1px solid var(--color-border);
  padding-top: 2rem;
}

.empty {
  color: var(--color-text-muted, #888);
  font-style: italic;
}

.accounts-table-wrap {
  overflow-x: auto;
}

.accounts-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.accounts-table th,
.accounts-table td {
  padding: 0.6rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.accounts-table th {
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  color: var(--color-text-muted, #888);
}

.col-check {
  text-align: center;
  width: 60px;
}

.col-email {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-actions {
  white-space: nowrap;
}

.check-mark {
  color: #16a34a;
  font-weight: bold;
}

.status-badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  white-space: nowrap;
}

.status-ok {
  background: #d1fae5;
  color: #065f46;
}

.status-warn {
  background: #fef3c7;
  color: #92400e;
}

.btn-action {
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-background);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.8rem;
  margin-right: 0.3rem;
}

.btn-action:hover {
  background: var(--color-background-soft);
}

.btn-delete {
  color: #dc2626;
  border-color: #dc2626;
}

.btn-delete:hover {
  background: #dc2626;
  color: #fff;
}

/* Add account section */
.add-account-section {
  margin-top: 1.5rem;
}

.add-buttons {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.btn {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
}

.connect-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.connect-btn.google {
  background: #4285f4;
  color: #fff;
}

.connect-btn.o365 {
  background: #2f2f2f;
  color: #fff;
}

.connect-btn.todoist {
  background: #e44332;
  color: #fff;
}

/* Modals */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1.5rem;
  min-width: 400px;
  max-width: 500px;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 1rem;
}

.modal-field label {
  font-weight: 600;
  font-size: 0.85rem;
}

.modal-field input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.9rem;
}

.modal-field input:disabled {
  opacity: 0.6;
}

.help-text {
  font-size: 0.75rem;
  color: var(--color-text-muted, #888);
}

.test-result {
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  font-size: 0.85rem;
}

.test-result.success {
  background: #d1fae5;
  color: #065f46;
}

.test-result.error {
  background: #fee2e2;
  color: #991b1b;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.btn-secondary {
  background: var(--color-background-soft);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.btn-primary {
  background: var(--color-text);
  color: var(--color-background);
}

.btn-danger {
  background: #dc2626;
  color: #fff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.warning-text {
  color: #92400e;
  font-size: 0.85rem;
  margin: 0.5rem 0;
}
</style>
