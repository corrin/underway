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
  <div class="chat-message" :class="[`chat-message--${role}`]" data-automation-id="chat-message">
    <div v-if="role === 'tool'" class="chat-message__tool" data-automation-id="chat-message-tool-output">
      <details>
        <summary>Tool output</summary>
        <pre class="chat-message__pre">{{ content }}</pre>
      </details>
    </div>
    <div v-else class="chat-message__content" v-html="renderedContent" />
    <div v-if="toolCalls && toolCalls.length > 0" class="chat-message__tool-calls" data-automation-id="chat-message-tool-calls">
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
  border-radius: 1rem;
  max-width: 80%;
}

.chat-message--user {
  background: var(--color-primary);
  color: #fff;
  align-self: flex-end;
  border-bottom-right-radius: 0.25rem;
}

.chat-message--assistant {
  background: var(--color-background-mute);
  color: var(--color-text);
  align-self: flex-start;
  border-bottom-left-radius: 0.25rem;
}

.chat-message--tool {
  background: var(--color-background-soft);
  color: var(--color-text);
  align-self: flex-start;
  font-size: 0.85rem;
}

/* User message overrides use hard-coded colors intentionally — they are
   relative to the blue bubble background, not the page theme. These stay
   fixed in both light and dark modes. */
.chat-message--user :deep(a) {
  color: #cfe2ff;
  text-decoration: underline;
}

.chat-message--user :deep(code) {
  color: #fff;
  background: rgba(255, 255, 255, 0.15);
}

.chat-message--user :deep(pre) {
  background: rgba(255, 255, 255, 0.12);
}

.chat-message__content :deep(p) {
  margin: 0.25rem 0;
}

.chat-message__content :deep(pre) {
  background: var(--color-surface-shadow);
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
  background: var(--color-surface-shadow);
  font-weight: 600;
}

.chat-message__pre {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.8rem;
  margin: 0.5rem 0 0;
  background: var(--color-surface-shadow);
  padding: 0.5rem;
  border-radius: 4px;
}

.chat-message__tool-calls {
  margin-top: 0.5rem;
  font-size: 0.85rem;
}
</style>
