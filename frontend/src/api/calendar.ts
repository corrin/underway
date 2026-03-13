import api from '@/api/client'

export interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
  location: string | null
  description: string | null
  provider: string
}

export interface ExternalAccount {
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

export async function fetchEvents(
  start?: string,
  end?: string,
): Promise<{ events: CalendarEvent[]; message?: string }> {
  const params: Record<string, string> = {}
  if (start) params.start = start
  if (end) params.end = end
  const response = await api.get('/calendar/events', { params })
  return response.data
}

export async function createEvent(data: {
  title: string
  start: string
  end: string
  location?: string
  description?: string
}): Promise<{ event: CalendarEvent }> {
  const response = await api.post('/calendar/create-event', data)
  return response.data
}

export async function deleteEvent(eventId: string): Promise<void> {
  await api.delete('/calendar/delete-event', { params: { event_id: eventId } })
}

export async function setPrimaryCalendar(accountId: string): Promise<void> {
  await api.post('/calendar/set-primary', { account_id: accountId })
}

export async function fetchAccounts(): Promise<ExternalAccount[]> {
  const response = await api.get('/external-accounts')
  return response.data
}

export async function initiateGoogleOAuth(): Promise<{ authorization_url: string }> {
  const response = await api.post('/oauth/google/initiate')
  return response.data
}

export async function initiateO365OAuth(): Promise<{ authorization_url: string }> {
  const response = await api.post('/oauth/o365/initiate')
  return response.data
}
