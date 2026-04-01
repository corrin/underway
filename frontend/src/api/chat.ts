import api from '@/api/client'

export interface Conversation {
  id: string
  user_id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'tool'
  content: string | null
  tool_calls: unknown[] | null
  tool_call_id: string | null
  sequence: number
  created_at: string
}

export interface DashboardTask {
  id: string
  title: string
  status: string
  priority: number | null
  due_date: string | null
  list_type: string | null
  position: number | null
}

export interface DashboardData {
  tasks: {
    prioritized: DashboardTask[]
    unprioritized: DashboardTask[]
    completed: DashboardTask[]
  }
  events: unknown[]
}

export interface SSEEvent {
  type: 'token' | 'tool_call' | 'dashboard_refresh' | 'done' | 'error'
  content?: string
  name?: string
  result?: unknown
  conversation_id?: string
  message?: string
}

export async function fetchConversations(): Promise<Conversation[]> {
  const response = await api.get('/conversations')
  return response.data
}

export async function createConversation(title?: string): Promise<Conversation> {
  const response = await api.post('/conversations', { title })
  return response.data
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/conversations/${id}`)
}

export async function fetchMessages(conversationId: string): Promise<ChatMessage[]> {
  const response = await api.get(`/conversations/${conversationId}/messages`)
  return response.data
}

export async function fetchDashboard(): Promise<DashboardData> {
  const response = await api.get('/dashboard')
  return response.data
}

export async function sendMessage(
  message: string,
  conversationId?: string,
  onEvent?: (event: SSEEvent) => void,
): Promise<void> {
  const token = localStorage.getItem('token')
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  })

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data: ')) continue
      try {
        const event: SSEEvent = JSON.parse(trimmed.slice(6))
        onEvent?.(event)
      } catch {
        // skip malformed events
      }
    }
  }
}
