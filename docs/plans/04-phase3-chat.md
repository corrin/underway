# Phase 3: Chat System — COMPLETED 2026-03-08

**Goal:** Port the chat system with SSE streaming, LLM tool calling, conversation management, and the Vue chat interface.

**Status:** All tasks complete. All quality gates passing.

## What was built

### Backend
- **Chat streaming endpoint** (`underway/chat/streaming.py`) — `POST /api/chat` returning SSE via `StreamingResponse`. Uses `litellm.acompletion()` with async streaming. Contains the agentic tool-calling loop (max 10 rounds).
- **Tool system** (`underway/chat/tools.py`) — 5 tool definitions in OpenAI function-calling format: `get_tasks`, `complete_task`, `create_task`, `update_task`, `get_calendar` (stub). All handlers async with session parameter. Mutating tools trigger `dashboard_refresh` SSE events.
- **Conversation ViewSet** (`underway/viewsets/chat.py`) — FastREST ModelViewSet for conversation CRUD + message history action. User-scoped queries.
- **Serializers** (`underway/serializers/chat.py`) — `ConversationSerializer`, `ChatMessageSerializer`, `ChatInputSerializer` with validation.
- **Dashboard endpoint** (`underway/chat/streaming.py`) — `GET /api/dashboard` returning tasks grouped by list + empty calendar events stub.

### Frontend
- **ChatView.vue** — Three-column layout: conversation sidebar, chat area with streaming messages, dashboard sidebar (tasks + calendar placeholder)
- **ChatMessage.vue** — Markdown rendering via `markdown-it`, collapsible tool call results, role-specific styling
- **Pinia store** (`stores/chat.ts`) — Conversation state, SSE event handling via `fetch` + `ReadableStream`, dashboard loading
- **API client** (`api/chat.ts`) — Typed wrappers for conversations, messages, dashboard, and SSE chat endpoint

### SSE Event Protocol

| Event Type | Payload | Purpose |
|-----------|---------|---------|
| `token` | `{type: "token", content: "..."}` | Streamed text token |
| `tool_call` | `{type: "tool_call", name: "...", result: {...}}` | Tool execution result |
| `dashboard_refresh` | `{type: "dashboard_refresh"}` | Signal UI to refresh sidebar |
| `done` | `{type: "done", conversation_id: "..."}` | Stream complete |
| `error` | `{type: "error", message: "..."}` | Error occurred |

### Tests
- Unit: tool definitions, tool handlers (get_tasks, complete_task, create_task, update_task), serializer validation
- Integration: SSE streaming, conversation persistence, tool calling loop, dashboard endpoint, user scoping
- E2E: chat page loads, input area visible, new chat button, dashboard sidebar

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/conversations` | List user's conversations |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations/{pk}` | Get conversation |
| DELETE | `/api/conversations/{pk}` | Delete conversation |
| GET | `/api/conversations/{pk}/messages` | Get message history |
| POST | `/api/chat` | Send message, returns SSE stream |
| GET | `/api/dashboard` | Tasks (real) + calendar (stub) |

## Key decisions
- `litellm.acompletion()` directly instead of AIManager/OpenAIProvider — litellm already abstracts across providers
- SSE only, no JSON response fallback — Vue SPA always uses streaming
- `get_calendar` tool returns empty events (stub until Phase 4) — tool list stays complete so LLM won't hallucinate calendar data
- `markdown-it` for rendering — lightweight with good table support
- Messages persisted with sequence numbers: user, assistant, and tool messages all saved as separate `ChatMessage` rows
