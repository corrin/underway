<script setup lang="ts">
import { onMounted } from 'vue'
import { useCalendarStore } from '@/stores/calendar'

const calendar = useCalendarStore()

onMounted(() => {
  calendar.loadEvents()
})
</script>

<template>
  <div class="calendar-page">
    <h1>Calendar</h1>

    <section class="events-section">
      <h2>Upcoming Events</h2>

      <div v-if="calendar.loading" class="loading">Loading events...</div>

      <div v-else-if="calendar.error" class="error">{{ calendar.error }}</div>

      <div v-else-if="calendar.events.length === 0" class="empty-state">
        <p>No upcoming events.</p>
      </div>

      <div v-else class="events-list">
        <div v-for="event in calendar.events" :key="event.id" class="event-card" :data-automation-id="`calendar-event-card-${event.id}`">
          <div class="event-time">
            <span class="event-date">{{ formatDate(event.start) }}</span>
            <span class="event-hours">{{ formatTime(event.start) }} - {{ formatTime(event.end) }}</span>
          </div>
          <div class="event-details">
            <strong class="event-title">{{ event.title }}</strong>
            <span v-if="event.location" class="event-location">{{ event.location }}</span>
          </div>
          <div class="event-provider">
            <span class="badge">{{ event.provider === 'google' ? 'Google' : 'O365' }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script lang="ts">
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped>
.calendar-page {
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

.events-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}

.event-time {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 120px;
}

.event-date {
  font-size: 0.8rem;
  color: var(--color-text-muted, #888);
}

.event-hours {
  font-size: 0.85rem;
  font-weight: 500;
}

.event-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.event-title {
  font-size: 0.95rem;
}

.event-location {
  font-size: 0.8rem;
  color: var(--color-text-muted, #888);
}

.event-provider {
  flex-shrink: 0;
}

.badge {
  font-size: 0.75rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  background: var(--color-background-soft);
  border: 1px solid var(--color-border);
}

.empty-state {
  color: var(--color-text-muted, #888);
  font-style: italic;
  padding: 1rem 0;
}

.loading {
  color: var(--color-text-muted, #888);
  padding: 1rem 0;
}

.error {
  color: #dc2626;
  padding: 1rem 0;
}
</style>
