<script setup lang="ts">
import type { Task } from '@/api/tasks'

const props = defineProps<{
  task: Task
}>()

const emit = defineEmits<{
  toggleStatus: [task: Task]
  delete: [task: Task]
}>()

function formatDate(date: string | null): string {
  if (!date) return ''
  return new Date(date).toLocaleDateString()
}

function priorityLabel(priority: number | null): string {
  if (priority === null) return ''
  const labels: Record<number, string> = { 1: 'Low', 2: 'Normal', 3: 'High', 4: 'Urgent' }
  return labels[priority] ?? `P${priority}`
}

function priorityClass(priority: number | null): string {
  if (priority === null) return ''
  if (priority >= 4) return 'priority-urgent'
  if (priority >= 3) return 'priority-high'
  return 'priority-normal'
}
</script>

<template>
  <div class="task-card" :class="{ completed: props.task.status === 'completed' }" :data-automation-id="`task-card-${props.task.id}`">
    <div class="task-main">
      <button
        class="status-toggle"
        :data-automation-id="`task-card-toggle-${props.task.id}`"
        :title="props.task.status === 'completed' ? 'Mark active' : 'Mark completed'"
        @click.stop="emit('toggleStatus', props.task)"
      >
        <span v-if="props.task.status === 'completed'" class="check">&#10003;</span>
        <span v-else class="circle"></span>
      </button>
      <div class="task-content">
        <span class="task-title" :data-automation-id="`task-card-title-${props.task.id}`">{{ props.task.title }}</span>
        <div class="task-meta">
          <span v-if="props.task.due_date" class="due-date">{{ formatDate(props.task.due_date) }}</span>
          <span v-if="props.task.priority" class="priority-badge" :class="priorityClass(props.task.priority)">
            {{ priorityLabel(props.task.priority) }}
          </span>
          <span v-if="props.task.project_name" class="project-name">{{ props.task.project_name }}</span>
          <span v-if="props.task.provider !== 'local'" class="provider-badge">{{ props.task.provider }}</span>
        </div>
      </div>
    </div>
    <button class="delete-btn" :data-automation-id="`task-card-delete-${props.task.id}`" title="Delete task" @click.stop="emit('delete', props.task)">&#215;</button>
  </div>
</template>

<style scoped>
.task-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-background);
  cursor: grab;
  transition: background-color 0.15s;
}

.task-card:hover {
  background: var(--color-background-soft);
}

.task-card.completed .task-title {
  text-decoration: line-through;
  opacity: 0.6;
}

.task-main {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  min-width: 0;
}

.status-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 1rem;
  line-height: 1;
  flex-shrink: 0;
}

.circle {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--color-border);
  border-radius: 50%;
}

.check {
  display: inline-block;
  width: 18px;
  height: 18px;
  text-align: center;
  line-height: 18px;
  color: #22c55e;
  font-weight: bold;
}

.task-content {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.task-title {
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-text-muted, #888);
}

.priority-badge {
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 600;
}

.priority-normal {
  background: #dbeafe;
  color: #1e40af;
}

.priority-high {
  background: #fef3c7;
  color: #92400e;
}

.priority-urgent {
  background: #fee2e2;
  color: #991b1b;
}

.provider-badge {
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
  font-size: 0.7rem;
}

.delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted, #888);
  font-size: 1.2rem;
  padding: 0 0.25rem;
  opacity: 0;
  transition: opacity 0.15s;
}

.task-card:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
}
</style>
