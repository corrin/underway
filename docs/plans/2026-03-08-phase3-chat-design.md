# Phase 3: Chat System — Design

## Architecture

The chat system adds three backend components and one frontend view.

### Backend

- **Chat streaming endpoint** (`underway/chat/streaming.py`) — `POST /api/chat` returning SSE. Uses `litellm.acompletion()` directly with async streaming. Contains the agentic tool-calling loop.
- **Conversation ViewSet** (`underway/viewsets/chat.py`) — Standard CRUD for conversations + message history action. Uses FastREST ModelViewSet.
- **Tool system** (`underway/chat/tools.py`) — 5 tool definitions (get_tasks, complete_task, create_task, update_task, get_calendar). All handlers async with session parameter. get_calendar is a stub returning empty events.
- **Dashboard endpoint** — `GET /api/dashboard` returning tasks (real) + calendar (empty stub).

### Frontend

- **ChatView.vue** — Split layout: chat area + task/calendar sidebar.
- **ChatMessage.vue** — Renders markdown via `markdown-it` (with table support), collapsible tool call results.
- **Pinia store** (`stores/chat.ts`) — Conversation state, SSE message handling via `fetch` + `ReadableStream`.
- **API client** (`api/chat.ts`) — Typed wrappers for conversations and dashboard.

## SSE Flow

```
Client POST /api/chat {message, conversation_id?}
  → Save user message
  → Build messages (system prompt + history + user message)
  → Loop:
      → litellm.acompletion(stream=True)
      → Yield token events as chunks arrive
      → If tool_calls: execute tools, yield tool_call events
        → If mutating tool: yield dashboard_refresh
        → Append tool results to messages, continue loop
      → If no tool_calls: yield done event, break
```

### SSE Event Protocol

| Event Type | Payload | Purpose |
|-----------|---------|---------|
| `token` | `{type: "token", content: "..."}` | Streamed text token |
| `tool_call` | `{type: "tool_call", name: "...", result: {...}}` | Tool execution result |
| `dashboard_refresh` | `{type: "dashboard_refresh"}` | Signal UI to refresh sidebar |
| `done` | `{type: "done", conversation_id: "..."}` | Stream complete |
| `error` | `{type: "error", message: "..."}` | Error occurred |

## Data Flow

Conversation and ChatMessage models already exist from Phase 1. Message persistence follows the original pattern:

- User message saved on receipt
- Assistant messages saved after each LLM response
- Tool call/result pairs saved as separate ChatMessage rows matching OpenAI's format
- Sequence numbers ensure correct ordering

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/conversations` | List user's conversations |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations/{pk}` | Get conversation |
| DELETE | `/api/conversations/{pk}` | Delete conversation |
| GET | `/api/conversations/{pk}/messages` | Get message history |
| POST | `/api/chat` | Send message, returns SSE stream |
| GET | `/api/dashboard` | Tasks (real) + calendar (stub) |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM abstraction | `litellm.acompletion()` directly | litellm already abstracts across providers; AIManager/OpenAIProvider are redundant |
| Response mode | SSE only | Vue SPA always uses streaming; JSON fallback has no consumer |
| Dashboard | Tasks real, calendar stub | Calendar providers come in Phase 4; sidebar UI is ready now |
| get_calendar tool | Stub returning empty events | Tool list stays complete; LLM won't hallucinate calendar data |
| Markdown rendering | `markdown-it` with table plugin | Lightweight, fast, good table support |

## Files to Create/Modify

| File | Action |
|------|--------|
| `underway/chat/streaming.py` | New — chat endpoint + SSE generator + dashboard |
| `underway/chat/tools.py` | New — tool definitions + async handlers |
| `underway/viewsets/chat.py` | New — ConversationViewSet |
| `underway/serializers/chat.py` | New — Conversation, ChatMessage, ChatInput serializers |
| `underway/app.py` | Modify — register new routes + viewset |
| `frontend/src/views/ChatView.vue` | New — chat page with sidebar |
| `frontend/src/components/ChatMessage.vue` | New — markdown + tool results |
| `frontend/src/stores/chat.ts` | New — Pinia store with SSE handling |
| `frontend/src/api/chat.ts` | New — API client |
| `frontend/src/router/index.ts` | Modify — add chat route |
| `frontend/package.json` | Modify — add markdown-it |

## What We're NOT Porting

- AIManager / OpenAIProvider — litellm handles provider abstraction
- JSON response mode — SSE only, no consumer for JSON fallback
- Calendar provider logic in get_calendar — stub until Phase 4

## Testing Strategy

### Unit tests
- Tool execution: mock DB session, test each handler (get_tasks, complete_task, create_task, update_task, get_calendar stub)
- SSE event formatting: verify each event type produces correct `data:` lines
- Message building: system prompt + user instructions + history + new message

### Integration tests
- Conversation CRUD endpoints (list, create, get, delete)
- Message history endpoint (`GET /api/conversations/{id}/messages`)
- `POST /api/chat` with mocked litellm — verify SSE events stream correctly
- Tool calling loop: mock litellm to return tool_call, then final response — verify full loop
- Messages persisted correctly (user + assistant + tool messages with proper sequencing)
- Dashboard endpoint returns tasks + empty calendar
- User scoping: can't access other users' conversations

### E2E tests (Playwright)
- Chat page loads with input field and sidebar
- Send message, see streamed response appear (mock litellm in test env)
- Conversation appears in conversation list
- New conversation button works
- Dashboard sidebar shows tasks
