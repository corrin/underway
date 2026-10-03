<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import api from '@/api/client'

const props = defineProps<{ refreshing: boolean }>()
type Block = { id: string; title: string; start: string; end: string; reason: string; protected: boolean }
type Progress = { node_id: string; minutes: number; percentage_of_recorded_time: number; target_percentage: number | null }
const blocks = ref<Block[]>([])
const progress = ref<Progress[]>([])
const titles = ref<Record<string, string>>({})
const enabled = ref(false)
const loading = ref(false)
const error = ref('')
const warnings = ref<string[]>([])
async function load() {
  try {
    const [schedule, intentions] = await Promise.all([api.get('/schedule'), api.get('/intentions')])
    blocks.value = schedule.data.blocks
    progress.value = schedule.data.progress
    enabled.value = schedule.data.enabled
    error.value = schedule.data.error || ''
    warnings.value = schedule.data.warnings || []
    titles.value = Object.fromEntries(intentions.data.nodes.map((n: { id: string; title: string }) => [n.id, n.title]))
  } catch { error.value = 'Unable to read the schedule. Check connected accounts in Settings.' }
}
async function rebuild() {
  loading.value = true
  try {
    const result = await api.post('/schedule/rebuild')
    warnings.value = result.data.warnings || []
    await load()
  } catch { error.value = 'Schedule refresh failed. Please retry.' } finally { loading.value = false }
}
function dateTime(value: string) {
  return new Date(value).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })
}
watch(() => props.refreshing, (active, previous) => { if (previous && !active) load() })
onMounted(load)
</script>

<template>
  <section class="weekly-queue">
    <h4>This week's suggestions</h4>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!enabled">Configure activity intentions in Settings to start your weekly queue.</p>
    <template v-else>
      <button :disabled="loading" @click="rebuild">{{ loading ? 'Refreshing…' : 'Refresh suggestions' }}</button>
      <p v-for="warning in warnings" :key="warning" role="status">{{ warning }}</p>
      <p v-if="blocks.length === 0">No suggestions published yet.</p>
      <details v-if="blocks.length"><summary>{{ blocks.length }} upcoming slots</summary>
        <article v-for="block in blocks" :key="block.id">
          <small>{{ dateTime(block.start) }} – {{ dateTime(block.end) }}</small>
          <strong>{{ block.title }}</strong>
          <small>{{ block.reason }}{{ block.protected ? ' · Kept in place' : '' }}</small>
        </article>
      </details>
      <h4>Reported time this week</h4>
      <p>Tell me what you did in chat. Suggestions only count once you report them.</p>
      <ul><li v-for="row in progress" :key="row.node_id">
        {{ titles[row.node_id] }}: {{ row.minutes }} minutes · {{ row.percentage_of_recorded_time.toFixed(0) }}% of recorded time
        <span v-if="row.target_percentage !== null"> · {{ row.target_percentage.toFixed(0) }}% of weekly minimum</span>
      </li></ul>
    </template>
  </section>
</template>

<style scoped>
.weekly-queue { margin-bottom: 1.5rem; font-size: .85rem; }
h4 { border-bottom: 2px solid var(--color-border); padding-bottom: .4rem; }
article { display: flex; flex-direction: column; gap: .3rem; padding: .6rem; margin: .4rem 0; background: var(--color-background); border-radius: 4px; }
button { padding: .4rem .7rem; color: var(--color-text); background: var(--color-background); border: 1px solid var(--color-border); border-radius: 4px; cursor: pointer; }
summary { cursor: pointer; margin: .5rem 0; }
ul { padding-left: 1rem; }
li { margin: .4rem 0; }
</style>
