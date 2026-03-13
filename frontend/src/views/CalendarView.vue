<script setup lang="ts">
import { onMounted } from 'vue'
import { useCalendarStore } from '@/stores/calendar'

const calendar = useCalendarStore()

onMounted(() => {
  calendar.loadAccounts()
  calendar.loadEvents()
})
</script>

<template>
  <div class="calendar-page">
    <h1>Calendar</h1>

    <!-- Connected accounts -->
    <section class="accounts-section">
      <h2>Connected Calendars</h2>

      <div v-if="calendar.accounts.length === 0" class="empty-state">
        <p>No calendar accounts connected yet.</p>
      </div>

      <div v-for="account in calendar.accounts" :key="account.id" class="account-card">
        <div class="account-info">
          <strong class="provider-name">{{ account.provider === 'google' ? 'Google' : 'Microsoft 365' }}</strong>
          <span class="account-email">{{ account.external_email }}</span>
        </div>
        <div class="account-actions">
          <span v-if="account.is_primary_calendar" class="badge primary">Primary</span>
          <button
            v-else
            class="btn-small"
            @click="calendar.setPrimary(account.id)"
          >
            Set Primary
          </button>
          <span v-if="account.needs_reauth" class="badge warning">Needs re-auth</span>
        </div>
      </div>

      <div class="connect-buttons">
        <button class="btn connect-btn google" @click="calendar.connectGoogle()">
          Connect Google Calendar
        </button>
        <button class="btn connect-btn o365" @click="calendar.connectO365()">
          Connect Microsoft 365
        </button>
      </div>
    </section>

    <!-- Events -->
    <section class="events-section">
      <h2>Upcoming Events</h2>

      <div v-if="calendar.loading" class="loading">Loading events...</div>

      <div v-else-if="calendar.error" class="error">{{ calendar.error }}</div>

      <div v-else-if="calendar.events.length === 0" class="empty-state">
        <p>No upcoming events.</p>
      </div>

      <div v-else class="events-list">
        <div v-for="event in calendar.events" :key="event.id" class="event-card">
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

.accounts-section {
  margin-bottom: 2.5rem;
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

.provider-name {
  text-transform: capitalize;
}

.account-email {
  font-size: 0.85rem;
  color: var(--color-text-muted, #888);
}

.account-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.connect-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.btn {
  padding: 0.6rem 1.2rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.9rem;
}

.connect-btn.google {
  background: #4285f4;
  color: #fff;
}

.connect-btn.o365 {
  background: #0078d4;
  color: #fff;
}

.btn-small {
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-background);
  color: var(--color-text);
  cursor: pointer;
  font-size: 0.8rem;
}

.events-section {
  border-top: 1px solid var(--color-border);
  padding-top: 2rem;
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

.badge.primary {
  background: #dbeafe;
  color: #1d4ed8;
  border-color: #93c5fd;
}

.badge.warning {
  background: #fef3c7;
  color: #92400e;
  border-color: #f59e0b;
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
