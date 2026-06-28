<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import ChatMessage from '@/components/ChatMessage.vue'
import { useChatStore, type DashboardTask } from '@/stores/chat'
import { useCalendarStore } from '@/stores/calendar'

const store = useChatStore()
const calendarStore = useCalendarStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const sidebarOpen = ref(false)

onMounted(() => {
  store.loadConversations()
  store.loadDashboard()

  const now = new Date()
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString()
  const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).toISOString()
  calendarStore.loadEvents(startOfDay, endOfDay)
})

const todayEvents = computed(() => calendarStore.events)

watch(
  () => store.messages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      } else {
        // no-op: container not yet mounted
      }
    })
  },
)

watch(
  () => store.streamingContent,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      } else {
        // no-op: container not yet mounted
      }
    })
  },
)

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || store.isStreaming) return
  inputText.value = ''
  await store.send(text)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  } else {
    // no-op: other keys handled by textarea default behavior
  }
}

function formatTime(dateStr: string) {
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function priorityClass(task: DashboardTask) {
  if (task.priority === 1) return 'priority-p1'
  if (task.priority === 2) return 'priority-p2'
  if (task.priority === 3) return 'priority-p3'
  return 'priority-p4'
}

function priorityLabel(task: DashboardTask) {
  if (task.priority === 1) return 'P1'
  if (task.priority === 2) return 'P2'
  if (task.priority === 3) return 'P3'
  return 'P4'
}
</script>

<template>
  <div class="chat-layout">
    <!-- Collapsible conversation sidebar -->
    <aside class="chat-sidebar chat-sidebar--left" :class="{ open: sidebarOpen }">
      <button class="btn-new-chat" @click="store.startNewConversation()">+ New Chat</button>
      <div class="conversation-list">
        <div
          v-for="conv in store.conversations"
          :key="conv.id"
          class="conversation-item"
          :class="{ active: store.currentConversation?.id === conv.id }"
          @click="store.selectConversation(conv)"
        >
          <span class="conversation-title">{{ conv.title || 'Untitled' }}</span>
          <button
            class="conversation-delete"
            title="Delete conversation"
            @click.stop="store.removeConversation(conv.id)"
          >
            &times;
          </button>
        </div>
      </div>
    </aside>

    <!-- Chat area -->
    <main class="chat-main">
      <div v-if="store.error" class="chat-error">{{ store.error }}</div>

      <div ref="messagesContainer" class="chat-messages">
        <div v-if="store.messages.length === 0 && !store.isStreaming" class="chat-empty">
          Start a conversation by sending a message.
        </div>
        <ChatMessage
          v-for="msg in store.messages"
          :key="msg.id"
          :role="msg.role"
          :content="msg.content"
          :tool-calls="msg.tool_calls"
        />
        <div v-if="store.streamingContent" class="streaming-message">
          <ChatMessage role="assistant" :content="store.streamingContent" :tool-calls="null" />
        </div>
        <div v-if="store.isStreaming && !store.streamingContent" class="chat-typing">
          Assistant is thinking...
        </div>
      </div>

      <div class="chat-input-area">
        <button
          class="btn-sidebar-toggle"
          title="Toggle conversations"
          aria-label="Toggle conversations"
          @click="sidebarOpen = !sidebarOpen"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="3" y="5" width="14" height="1.5" rx="0.75" fill="currentColor" />
            <rect x="3" y="9.25" width="14" height="1.5" rx="0.75" fill="currentColor" />
            <rect x="3" y="13.5" width="14" height="1.5" rx="0.75" fill="currentColor" />
          </svg>
        </button>
        <textarea
          v-model="inputText"
          class="chat-input"
          placeholder="Type a message..."
          rows="1"
          :disabled="store.isStreaming"
          @keydown="handleKeydown"
        />
        <button
          class="btn-send"
          title="Send message"
          aria-label="Send message"
          :disabled="!inputText.trim() || store.isStreaming"
          @click="handleSend"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>
    </main>

    <!-- Dashboard sidebar -->
    <aside class="chat-sidebar chat-sidebar--right">
      <div class="dashboard-section">
        <h4 class="dashboard-section-title">Today's Calendar</h4>
        <div v-if="calendarStore.loading" class="dashboard-empty">Loading...</div>
        <div v-else-if="todayEvents.length === 0" class="dashboard-empty">No events today.</div>
        <div v-else class="dashboard-cards">
          <div v-for="event in todayEvents" :key="event.id" class="event-card">
            <div class="event-time">{{ formatTime(event.start) }} – {{ formatTime(event.end) }}</div>
            <div class="event-title">{{ event.title }}</div>
            <div v-if="event.location" class="event-location">{{ event.location }}</div>
          </div>
        </div>
      </div>

      <template v-if="store.dashboard">
        <div class="dashboard-section">
          <h4 class="dashboard-section-title">Prioritized Tasks</h4>
          <div v-if="store.dashboard.tasks.prioritized.length === 0" class="dashboard-empty">
            No prioritized tasks.
          </div>
          <div v-else class="dashboard-cards">
            <div
              v-for="task in (store.dashboard.tasks.prioritized as DashboardTask[])"
              :key="task.id"
              class="task-card"
            >
              <span class="priority-badge" :class="priorityClass(task)">
                {{ priorityLabel(task) }}
              </span>
              <span class="task-title">{{ task.title || 'Untitled task' }}</span>
            </div>
          </div>
        </div>

        <div class="dashboard-section">
          <h4 class="dashboard-section-title">Unprioritized Tasks</h4>
          <div v-if="store.dashboard.tasks.unprioritized.length === 0" class="dashboard-empty">
            No unprioritized tasks.
          </div>
          <div v-else class="dashboard-cards">
            <div
              v-for="task in (store.dashboard.tasks.unprioritized as DashboardTask[])"
              :key="task.id"
              class="task-card"
            >
              <span class="task-title">{{ task.title || 'Untitled task' }}</span>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="dashboard-empty">Loading dashboard...</div>
    </aside>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  height: calc(100vh - 60px);
  overflow: hidden;
  position: relative;
}

/* Left sidebar — collapsible overlay */
.chat-sidebar--left {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--color-border);
  padding: 1rem;
  overflow-y: auto;
  background: var(--color-background-soft);
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 10;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
}

.chat-sidebar--left.open {
  transform: translateX(0);
}

/* Right sidebar — dashboard panel */
.chat-sidebar--right {
  flex: 0 0 40%;
  border-left: 1px solid var(--color-border);
  padding: 1rem;
  overflow-y: auto;
  background: var(--color-background-soft);
}

.btn-new-chat {
  width: 100%;
  padding: 0.5rem;
  background: var(--color-text);
  color: var(--color-background);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
  margin-bottom: 0.75rem;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.conversation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.conversation-item:hover {
  background: var(--color-background-mute);
}

.conversation-item.active {
  background: var(--color-primary);
  color: #fff;
}

.conversation-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.conversation-delete {
  background: none;
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
  opacity: 0.4;
  padding: 0 0.2rem;
  color: inherit;
}

.conversation-delete:hover {
  opacity: 1;
  color: #dc2626;
}

/* Chat main area */
.chat-main {
  flex: 0 0 60%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.chat-error {
  padding: 0.5rem 1rem;
  background: #fee2e2;
  color: #991b1b;
  font-size: 0.85rem;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.chat-empty {
  text-align: center;
  color: var(--color-text-muted, #888);
  padding: 3rem 1rem;
  font-style: italic;
}

.chat-typing {
  color: var(--color-text-muted, #888);
  font-style: italic;
  padding: 0.5rem 1rem;
  align-self: flex-start;
}

.chat-input-area {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-background);
  align-items: flex-end;
}

.btn-sidebar-toggle {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-text-muted, #888);
  padding: 0.5rem;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-sidebar-toggle:hover {
  background: var(--color-background-mute);
  color: var(--color-text);
}

.chat-input {
  flex: 1;
  padding: 0.5rem 1rem;
  border: 1px solid var(--color-border);
  border-radius: 1.25rem;
  background: var(--color-background);
  color: var(--color-text);
  font-size: 0.9rem;
  resize: none;
  font-family: inherit;
}

.chat-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
}

.btn-send {
  width: 40px;
  height: 40px;
  min-width: 40px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-send:hover {
  background: var(--color-primary-hover);
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Dashboard sidebar */
.dashboard-section {
  margin-bottom: 1.25rem;
}

.dashboard-section-title {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
  font-weight: 600;
  padding-bottom: 0.4rem;
  border-bottom: 2px solid var(--color-border);
}

.dashboard-cards {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-card {
  background: var(--color-background);
  border-left: 4px solid var(--color-primary);
  border-radius: 0.25rem;
  padding: 0.5rem 0.75rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.event-time {
  font-size: 0.75rem;
  color: var(--color-text-muted, #6c757d);
  margin-bottom: 0.15rem;
}

.event-title {
  font-weight: 600;
  font-size: 0.85rem;
}

.event-location {
  font-size: 0.75rem;
  color: var(--color-text-muted, #6c757d);
  margin-top: 0.15rem;
}

.task-card {
  background: var(--color-background);
  border-radius: 0.25rem;
  padding: 0.5rem 0.75rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.task-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.priority-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.1rem 0.4rem;
  border-radius: 0.2rem;
  color: #fff;
  flex-shrink: 0;
}

.priority-p1 {
  background: #dc3545;
}

.priority-p2 {
  background: #fd7e14;
}

.priority-p3 {
  background: #ffc107;
  color: #212529;
}

.priority-p4 {
  background: #6c757d;
}

.dashboard-empty {
  font-size: 0.8rem;
  color: var(--color-text-muted, #888);
  font-style: italic;
}

/* Responsive */
@media (max-width: 768px) {
  .chat-layout {
    flex-direction: column;
  }

  /*
   * KNOWN ISSUE (mobile, needs proper design): hiding the right sidebar
   * removes the ONLY way to reach today's calendar and tasks below 768px —
   * there is currently no alternative surface for them on mobile. This is a
   * stopgap, not the intended behaviour. Proper fix: collapse the dashboard
   * (e.g. a toggle/drawer) or reflow it below the chat instead of removing it.
   * Flagged by CodeRabbit on PR #52.
   */
  .chat-sidebar--right {
    display: none;
  }

  .chat-main {
    flex: 1;
  }
}
</style>
