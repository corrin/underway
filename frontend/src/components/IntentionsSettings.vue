<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'
import api from '@/api/client'

type Window = { weekdays: number[]; start: string; end: string }
type Node = {
  id: string; parent_id: string | null; title: string; weekly_minutes: number | null
  interval_days: number | null; repeatable: boolean; [key: string]: unknown
}
type Intentions = {
  revision: number; enabled: boolean; timezone: string; slot_minutes: number
  calendar_provider: string | null; calendar_account: string | null
  schedule_calendar_id: string | null; activity_calendar_id: string | null
  allowed_windows: Window[]; nodes: Node[]; [key: string]: unknown
}
type Account = { provider: string; external_email: string; use_for_calendar: boolean; needs_reauth: boolean }
const document = ref<Intentions | null>(null)
const accounts = ref<Account[]>([])
const busy = ref(false)
const message = ref('')
const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function showError(error: unknown) {
  const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null
  message.value = typeof detail === 'string' ? detail : Array.isArray(detail)
    ? detail.map((item: { msg: string }) => item.msg).join('; ')
    : error instanceof Error ? error.message : 'Unable to save intentions'
}
async function load() {
  try {
    const [intentions, connections] = await Promise.all([api.get('/intentions'), api.get('/external-accounts')])
    document.value = intentions.data
    accounts.value = connections.data.filter((a: Account) => a.use_for_calendar && !a.needs_reauth)
  } catch (error) { showError(error) }
}
async function save() {
  busy.value = true
  message.value = ''
  try {
    const result = await api.put('/intentions', document.value)
    document.value = result.data.intentions
    message.value = result.data.schedule.error || (result.data.schedule.warnings || []).join(' ') || 'Saved'
  } catch (error) { showError(error) } finally { busy.value = false }
}
function selectAccount(event: Event) {
  const account = accounts.value[Number((event.target as HTMLSelectElement).value)]
  if (document.value && account) {
    document.value.calendar_provider = account.provider
    document.value.calendar_account = account.external_email
    document.value.schedule_calendar_id = null
    document.value.activity_calendar_id = null
  }
}
function addNode() {
  document.value?.nodes.push({ id: crypto.randomUUID(), parent_id: null, title: '', weekly_minutes: null,
    interval_days: null, repeatable: true })
}
function exportIntentions() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(document.value, null, 2)], { type: 'application/json' }))
  const link = window.document.createElement('a')
  link.href = url
  link.download = 'underway-intentions.json'
  link.click()
  URL.revokeObjectURL(url)
}
async function importIntentions(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !document.value) return
  try {
    const imported = JSON.parse(await file.text()) as Intentions
    imported.revision = document.value.revision
    imported.enabled = false
    if (!Array.isArray(imported.nodes) || !Array.isArray(imported.allowed_windows)) throw new Error('Invalid intentions file')
    document.value = imported
    message.value = 'Imported for review. Scheduling is off until you enable it and save.'
  } catch (error) { showError(error) }
}
function setNumber(node: Node, key: 'weekly_minutes' | 'interval_days', event: Event) {
  const value = (event.target as HTMLInputElement).value
  node[key] = value ? Number(value) : null
}
onMounted(load)
</script>

<template>
  <section class="intentions">
    <h2>Activity intentions</h2>
    <p>Set where you want your time to go. Use chat to link source projects, add preferred hours or record what you did.</p>
    <p v-if="message" role="status">{{ message }}</p>
    <form v-if="document" @submit.prevent="save">
      <label><input v-model="document.enabled" type="checkbox" /> Publish weekly suggestions</label>
      <label>Timezone <input v-model="document.timezone" required /></label>
      <label>Slot length <select v-model.number="document.slot_minutes"><option :value="30">30 minutes</option><option :value="60">60 minutes</option><option :value="120">120 minutes</option></select></label>
      <label>Calendar account
        <select :value="accounts.findIndex(a => a.provider === document?.calendar_provider && a.external_email === document?.calendar_account)" @change="selectAccount">
          <option :value="-1" disabled>Select an account</option>
          <option v-for="(account, index) in accounts" :key="account.provider + account.external_email" :value="index">{{ account.external_email }} ({{ account.provider }})</option>
        </select>
      </label>
      <p>Suggestions and reported activity use separate Underway calendars in this account.</p>
      <h3>Available hours</h3>
      <fieldset v-for="(window, index) in document.allowed_windows" :key="index">
        <legend>Window {{ index + 1 }}</legend>
        <div class="days"><label v-for="(day, number) in weekdays" :key="day"><input v-model="window.weekdays" type="checkbox" :value="number" />{{ day }}</label></div>
        <label>From <input v-model="window.start" type="time" required /></label>
        <label>Until <input v-model="window.end" type="time" required /></label>
        <button type="button" @click="document.allowed_windows.splice(index, 1)">Remove window</button>
      </fieldset>
      <button type="button" @click="document.allowed_windows.push({ weekdays: [0,1,2,3,4], start: '09:00', end: '17:00' })">Add available hours</button>
      <h3>Activity tree</h3>
      <fieldset v-for="node in document.nodes" :key="node.id">
        <legend>{{ node.title || 'New activity' }}</legend>
        <label>Activity <input v-model="node.title" required /></label>
        <label>Parent <select v-model="node.parent_id"><option :value="null">Top level</option><option v-for="parent in document.nodes.filter(n => n.id !== node.id)" :key="parent.id" :value="parent.id">{{ parent.title }}</option></select></label>
        <label>Weekly minimum (minutes) <input :value="node.weekly_minutes" type="number" min="1" @input="setNumber(node, 'weekly_minutes', $event)" /></label>
        <label>Catch up at least every (days) <input :value="node.interval_days" type="number" min="1" @input="setNumber(node, 'interval_days', $event)" /></label>
        <label><input v-model="node.repeatable" type="checkbox" /> Can suggest this activity without a task</label>
      </fieldset>
      <button type="button" @click="addNode">Add activity</button>
      <div class="actions"><button type="submit" :disabled="busy">{{ busy ? 'Saving…' : 'Save intentions' }}</button><button type="button" @click="exportIntentions">Export backup</button></div>
      <label>Import backup <input type="file" accept="application/json,.json" @change="importIntentions" /></label>
    </form>
  </section>
</template>

<style scoped>
.intentions { margin: 2rem 0; padding-top: 1rem; border-top: 1px solid var(--color-border); }
form, fieldset { display: flex; flex-direction: column; gap: .7rem; }
fieldset { border: 1px solid var(--color-border); border-radius: 6px; padding: 1rem; }
label { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
input, select, button { padding: .4rem; color: var(--color-text); background: var(--color-background); border: 1px solid var(--color-border); border-radius: 4px; }
.days, .actions { display: flex; gap: .5rem; flex-wrap: wrap; }
button { cursor: pointer; }
p { font-size: .9rem; }
</style>
