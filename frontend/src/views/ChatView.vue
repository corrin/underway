<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import ChatMessage from '@/components/ChatMessage.vue'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  store.loadConversations()
  store.loadDashboard()
})

watch(
  () => store.messages.length,
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
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
  }
}
</script>

<template>
  <div class="chat-layout">
    <!-- Conversation sidebar -->
    <aside class="chat-sidebar chat-sidebar--left">
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
          Thinking...
        </div>
      </div>

      <div class="chat-input-area">
        <textarea
          v-model="inputText"
          class="chat-input"
          placeholder="Type a message..."
          rows="2"
          :disabled="store.isStreaming"
          @keydown="handleKeydown"
        />
        <button
          class="btn-send"
          :disabled="!inputText.trim() || store.isStreaming"
          @click="handleSend"
        >
          Send
        </button>
      </div>
    </main>

    <!-- Dashboard sidebar -->
    <aside class="chat-sidebar chat-sidebar--right">
      <h3 class="sidebar-heading">Dashboard</h3>

      <template v-if="store.dashboard">
        <div class="dashboard-section">
          <h4>Prioritized</h4>
          <ul class="dashboard-list">
            <li v-for="(task, i) in store.dashboard.tasks.prioritized" :key="i">
              {{ (task as Record<string, unknown>).title || 'Untitled task' }}
            </li>
          </ul>
          <div v-if="store.dashboard.tasks.prioritized.length === 0" class="dashboard-empty">
            None
          </div>
        </div>

        <div class="dashboard-section">
          <h4>Unprioritized</h4>
          <ul class="dashboard-list">
            <li v-for="(task, i) in store.dashboard.tasks.unprioritized" :key="i">
              {{ (task as Record<string, unknown>).title || 'Untitled task' }}
            </li>
          </ul>
          <div v-if="store.dashboard.tasks.unprioritized.length === 0" class="dashboard-empty">
            None
          </div>
        </div>
      </template>

      <div v-else class="dashboard-empty">Loading dashboard...</div>

      <div class="dashboard-section">
        <h4>Calendar</h4>
        <div class="dashboard-empty">Coming soon</div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  height: calc(100vh - 60px);
  overflow: hidden;
}

/* Sidebars */
.chat-sidebar {
  border-right: 1px solid var(--color-border, #ddd);
  padding: 1rem;
  overflow-y: auto;
  background: var(--color-background-soft, #f9f9f9);
}

.chat-sidebar--right {
  border-right: none;
  border-left: 1px solid var(--color-border, #ddd);
}

.btn-new-chat {
  width: 100%;
  padding: 0.5rem;
  background: var(--color-text, #333);
  color: var(--color-background, #fff);
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
  background: var(--color-background-mute, #eee);
}

.conversation-item.active {
  background: #dbeafe;
  color: #1e40af;
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
}

.chat-input-area {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--color-border, #ddd);
  background: var(--color-background, #fff);
}

.chat-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  background: var(--color-background, #fff);
  color: var(--color-text, #333);
  font-size: 0.9rem;
  resize: none;
  font-family: inherit;
}

.btn-send {
  padding: 0.5rem 1.25rem;
  background: var(--color-text, #333);
  color: var(--color-background, #fff);
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
  align-self: flex-end;
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Dashboard sidebar */
.sidebar-heading {
  margin: 0 0 1rem;
  font-size: 1rem;
}

.dashboard-section {
  margin-bottom: 1rem;
}

.dashboard-section h4 {
  margin: 0 0 0.3rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.7;
}

.dashboard-list {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 0.85rem;
}

.dashboard-list li {
  padding: 0.3rem 0;
  border-bottom: 1px solid var(--color-border, #eee);
}

.dashboard-empty {
  font-size: 0.8rem;
  color: var(--color-text-muted, #888);
  font-style: italic;
}

/* Responsive */
@media (max-width: 768px) {
  .chat-layout {
    grid-template-columns: 1fr;
  }

  .chat-sidebar {
    display: none;
  }
}
</style>
