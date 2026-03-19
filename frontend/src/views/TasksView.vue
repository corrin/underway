<script setup lang="ts">
import { ref, onMounted } from 'vue'
import draggable from 'vuedraggable'
import TaskCard from '@/components/TaskCard.vue'
import { useTaskStore } from '@/stores/tasks'
import type { Task } from '@/api/tasks'

const store = useTaskStore()

const newTaskTitle = ref('')
const showAddForm = ref(false)

onMounted(() => {
  store.fetchTasks()
})

async function addTask() {
  const title = newTaskTitle.value.trim()
  if (!title) return
  await store.createTask(title)
  newTaskTitle.value = ''
  showAddForm.value = false
}

async function toggleStatus(task: Task) {
  const newStatus = task.status === 'completed' ? 'active' : 'completed'
  await store.updateStatus(task.id, newStatus)
}

async function deleteTask(task: Task) {
  await store.removeTask(task.id)
}

function onDragEnd(listType: string, list: Task[]) {
  const order = list.map((t, i) => ({ id: t.id, position: i }))
  store.reorder(listType, order)
}

function onMoveTask(evt: { added?: { element: Task }; removed?: unknown }, destination: string) {
  if (evt.added) {
    store.moveTaskToList(evt.added.element.id, destination, 0)
  }
}
</script>

<template>
  <div class="tasks-page">
    <div class="tasks-header">
      <h1>Tasks</h1>
      <div class="header-actions">
        <button class="btn-secondary" data-automation-id="tasks-sync-button" :disabled="store.syncing" @click="store.sync()">
          {{ store.syncing ? 'Syncing...' : 'Sync' }}
        </button>
        <button class="btn-primary" :data-automation-id="showAddForm ? 'tasks-cancel-button' : 'tasks-add-button'" @click="showAddForm = !showAddForm">
          {{ showAddForm ? 'Cancel' : '+ Add Task' }}
        </button>
      </div>
    </div>

    <div v-if="store.error" class="error-banner">
      {{ store.error }}
    </div>

    <form v-if="showAddForm" class="add-task-form" @submit.prevent="addTask">
      <input
        v-model="newTaskTitle"
        type="text"
        placeholder="Task title..."
        autofocus
        class="add-task-input"
        data-automation-id="tasks-add-input"
      />
      <button type="submit" class="btn-primary" data-automation-id="tasks-add-submit" :disabled="!newTaskTitle.trim()">Add</button>
    </form>

    <div v-if="store.loading" class="loading">Loading tasks...</div>

    <div v-else class="task-columns">
      <section class="task-column" data-automation-id="tasks-column-prioritized">
        <h2 class="column-header prioritized">Prioritized</h2>
        <draggable
          :list="store.prioritized"
          group="tasks"
          item-key="id"
          class="task-list"
          ghost-class="sortable-ghost"
          @change="(evt: Record<string, unknown>) => onMoveTask(evt as { added?: { element: Task } }, 'prioritized')"
          @end="() => onDragEnd('prioritized', store.prioritized)"
        >
          <template #item="{ element }">
            <TaskCard
              :task="element"
              @toggle-status="toggleStatus"
              @delete="deleteTask"
            />
          </template>
        </draggable>
        <div v-if="store.prioritized.length === 0" class="empty-list">No prioritized tasks</div>
      </section>

      <section class="task-column" data-automation-id="tasks-column-unprioritized">
        <h2 class="column-header unprioritized">Unprioritized</h2>
        <draggable
          :list="store.unprioritized"
          group="tasks"
          item-key="id"
          class="task-list"
          ghost-class="sortable-ghost"
          @change="(evt: Record<string, unknown>) => onMoveTask(evt as { added?: { element: Task } }, 'unprioritized')"
          @end="() => onDragEnd('unprioritized', store.unprioritized)"
        >
          <template #item="{ element }">
            <TaskCard
              :task="element"
              @toggle-status="toggleStatus"
              @delete="deleteTask"
            />
          </template>
        </draggable>
        <div v-if="store.unprioritized.length === 0" class="empty-list">No unprioritized tasks</div>
      </section>

      <section class="task-column" data-automation-id="tasks-column-completed">
        <h2 class="column-header completed-header">Completed</h2>
        <draggable
          :list="store.completed"
          group="tasks"
          item-key="id"
          class="task-list"
          ghost-class="sortable-ghost"
          @change="(evt: Record<string, unknown>) => onMoveTask(evt as { added?: { element: Task } }, 'completed')"
          @end="() => onDragEnd('completed', store.completed)"
        >
          <template #item="{ element }">
            <TaskCard
              :task="element"
              @toggle-status="toggleStatus"
              @delete="deleteTask"
            />
          </template>
        </draggable>
        <div v-if="store.completed.length === 0" class="empty-list">No completed tasks</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tasks-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem 1rem;
}

.tasks-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.tasks-header h1 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: var(--color-text);
  color: var(--color-background);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.5rem 1rem;
  background: none;
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-banner {
  padding: 0.75rem 1rem;
  background: #fee2e2;
  color: #991b1b;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.add-task-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.add-task-input {
  flex: 1;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.95rem;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: var(--color-text-muted, #888);
}

.task-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .task-columns {
    grid-template-columns: 1fr;
  }
}

.task-column {
  min-height: 200px;
}

.column-header {
  font-size: 0.9rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.5rem 0.75rem;
  border-radius: 6px 6px 0 0;
  margin-bottom: 0;
}

.column-header.prioritized {
  background: #dbeafe;
  color: #1e40af;
}

.column-header.unprioritized {
  background: var(--color-background-soft);
  color: var(--color-text);
}

.column-header.completed-header {
  background: #dcfce7;
  color: #166534;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 100px;
  padding: 0.5rem;
  border: 1px solid var(--color-border);
  border-top: none;
  border-radius: 0 0 6px 6px;
  background: var(--color-background-mute, #f5f5f5);
}

.empty-list {
  text-align: center;
  padding: 1.5rem;
  color: var(--color-text-muted, #888);
  font-size: 0.85rem;
  font-style: italic;
  border: 1px solid var(--color-border);
  border-top: none;
  border-radius: 0 0 6px 6px;
}

.sortable-ghost {
  opacity: 0.4;
  background: var(--color-background-soft) !important;
}
</style>
