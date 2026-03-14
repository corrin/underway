import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchEvents,
  fetchAccounts,
  createEvent,
  deleteEvent,
  type CalendarEvent,
  type ExternalAccount,
} from '@/api/calendar'

export const useCalendarStore = defineStore('calendar', () => {
  const events = ref<CalendarEvent[]>([])
  const accounts = ref<ExternalAccount[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadEvents(start?: string, end?: string) {
    loading.value = true
    error.value = null
    try {
      const data = await fetchEvents(start, end)
      events.value = data.events
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load events'
    } finally {
      loading.value = false
    }
  }

  async function loadAccounts() {
    try {
      const data = await fetchAccounts()
      accounts.value = data.filter((a) => a.use_for_calendar)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load accounts'
    }
  }

  async function addEvent(data: {
    title: string
    start: string
    end: string
    location?: string
    description?: string
  }) {
    const result = await createEvent(data)
    events.value.push(result.event)
    return result.event
  }

  async function removeEvent(eventId: string) {
    await deleteEvent(eventId)
    events.value = events.value.filter((e) => e.id !== eventId)
  }

  return {
    events,
    accounts,
    loading,
    error,
    loadEvents,
    loadAccounts,
    addEvent,
    removeEvent,
  }
})
