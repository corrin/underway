import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchConversations as apiFetchConversations,
  deleteConversation as apiDeleteConversation,
  fetchMessages as apiFetchMessages,
  fetchDashboard as apiFetchDashboard,
  sendMessage as apiSendMessage,
  type Conversation,
  type ChatMessage,
  type DashboardData,
  type SSEEvent,
} from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConversation = ref<Conversation | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streamingContent = ref('')
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  const dashboard = ref<DashboardData | null>(null)

  async function loadConversations() {
    error.value = null
    try {
      conversations.value = await apiFetchConversations()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load conversations'
    }
  }

  async function loadMessages(conversationId: string) {
    error.value = null
    try {
      messages.value = await apiFetchMessages(conversationId)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to load messages'
    }
  }

  async function selectConversation(conversation: Conversation) {
    currentConversation.value = conversation
    await loadMessages(conversation.id)
  }

  function startNewConversation() {
    currentConversation.value = null
    messages.value = []
    streamingContent.value = ''
  }

  async function removeConversation(id: string) {
    error.value = null
    try {
      await apiDeleteConversation(id)
      conversations.value = conversations.value.filter((c) => c.id !== id)
      if (currentConversation.value?.id === id) {
        startNewConversation()
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to delete conversation'
    }
  }

  async function send(messageText: string) {
    error.value = null
    isStreaming.value = true
    streamingContent.value = ''

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      conversation_id: currentConversation.value?.id ?? '',
      role: 'user',
      content: messageText,
      tool_calls: null,
      tool_call_id: null,
      sequence: messages.value.length,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMessage)

    try {
      await apiSendMessage(
        messageText,
        currentConversation.value?.id,
        (event: SSEEvent) => {
          switch (event.type) {
            case 'token':
              streamingContent.value += event.content ?? ''
              break
            case 'tool_call':
              // tool calls are rendered when the full message arrives
              break
            case 'dashboard_refresh':
              loadDashboard()
              break
            case 'done':
              if (event.conversation_id && !currentConversation.value) {
                const conv: Conversation = {
                  id: event.conversation_id,
                  user_id: '',
                  title: null,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                }
                currentConversation.value = conv
                conversations.value.unshift(conv)
              }
              if (streamingContent.value) {
                const assistantMessage: ChatMessage = {
                  id: crypto.randomUUID(),
                  conversation_id: currentConversation.value?.id ?? '',
                  role: 'assistant',
                  content: streamingContent.value,
                  tool_calls: null,
                  tool_call_id: null,
                  sequence: messages.value.length,
                  created_at: new Date().toISOString(),
                }
                messages.value.push(assistantMessage)
              }
              streamingContent.value = ''
              isStreaming.value = false
              loadConversations()
              break
            case 'error':
              error.value = event.message ?? 'An error occurred'
              isStreaming.value = false
              break
          }
        },
      )
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'Failed to send message'
      isStreaming.value = false
    }
  }

  async function loadDashboard() {
    try {
      dashboard.value = await apiFetchDashboard()
    } catch {
      // dashboard load failure is non-critical
    }
  }

  return {
    conversations,
    currentConversation,
    messages,
    streamingContent,
    isStreaming,
    error,
    dashboard,
    loadConversations,
    loadMessages,
    selectConversation,
    startNewConversation,
    removeConversation,
    send,
    loadDashboard,
  }
})
