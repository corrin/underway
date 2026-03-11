<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps<{
  role: string
  content: string | null
  toolCalls: unknown[] | null
}>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
})

const renderedContent = computed(() => {
  if (!props.content) return ''
  return md.render(props.content)
})
</script>

<template>
  <div class="chat-message" :class="[`chat-message--${role}`]">
    <div class="chat-message__role">{{ role }}</div>
    <div v-if="role === 'tool'" class="chat-message__tool">
      <details>
        <summary>Tool output</summary>
        <pre class="chat-message__pre">{{ content }}</pre>
      </details>
    </div>
    <div v-else class="chat-message__content" v-html="renderedContent" />
    <div v-if="toolCalls && toolCalls.length > 0" class="chat-message__tool-calls">
      <details>
        <summary>Tool calls ({{ toolCalls.length }})</summary>
        <pre class="chat-message__pre">{{ JSON.stringify(toolCalls, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

<style scoped>
.chat-message {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 0.5rem;
}

.chat-message--user {
  background: #dbeafe;
  color: #1e3a5f;
  margin-left: 2rem;
}

.chat-message--assistant {
  background: var(--color-background-soft, #f5f5f5);
  color: var(--color-text, #333);
  margin-right: 2rem;
}

.chat-message--tool {
  background: #f0fdf4;
  color: #14532d;
  margin-right: 2rem;
  font-size: 0.85rem;
}

.chat-message__role {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
  opacity: 0.6;
}

.chat-message__content :deep(p) {
  margin: 0.25rem 0;
}

.chat-message__content :deep(pre) {
  background: rgba(0, 0, 0, 0.05);
  padding: 0.5rem;
  border-radius: 4px;
  overflow-x: auto;
}

.chat-message__content :deep(code) {
  font-size: 0.85em;
}

.chat-message__content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
}

.chat-message__content :deep(th),
.chat-message__content :deep(td) {
  border: 1px solid var(--color-border, #ddd);
  padding: 0.4rem 0.6rem;
  text-align: left;
}

.chat-message__content :deep(th) {
  background: rgba(0, 0, 0, 0.05);
  font-weight: 600;
}

.chat-message__pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.8rem;
  margin: 0.5rem 0 0;
  background: rgba(0, 0, 0, 0.04);
  padding: 0.5rem;
  border-radius: 4px;
}

.chat-message__tool-calls {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}
</style>
