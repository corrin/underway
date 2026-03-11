# Phase 3: Chat System

## Goal

Port the chat system with SSE streaming, LLM tool calling, and conversation management. Build the Vue chat interface.

## Source Files

| Original | New |
|----------|-----|
| `chat/chat_routes.py` | `underway/viewsets/chat.py` + `underway/chat/streaming.py` |
| `chat/tools.py` | `underway/chat/tools.py` |
| `chat/models.py` | (already ported in Phase 1) |
| `ai/ai_manager.py` | `underway/providers/ai_manager.py` |
| `ai/openai_provider.py` | `underway/providers/openai_provider.py` |
| `templates/chat.html` | `frontend/src/views/ChatView.vue` |

## Steps

### 3.1 Conversation Serializers

```python
# underway/serializers/chat.py

class ConversationSerializer(ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

class ChatMessageSerializer(ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "tool_calls", "tool_call_id", "sequence", "created_at"]
        read_only_fields = ["id", "created_at"]

class ChatInputSerializer(Serializer):
    message = CharField(required=True)
    conversation_id = UUIDField(required=False)
```

### 3.2 Conversation ViewSet

Standard CRUD for conversation management:

```python
class ConversationViewSet(ModelViewSet):
    queryset = Conversation
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["-updated_at"]

    def get_queryset(self):
        return Conversation.query.filter_by(user_id=self.request.user.id)

    @action(methods=["get"], detail=True, url_path="messages")
    async def messages(self, request, **kwargs):
        """GET /api/conversations/{pk}/messages — full message history."""
        ...
```

### 3.3 Chat Endpoint (Non-ViewSet)

The chat endpoint doesn't fit CRUD patterns — it's a stateful streaming endpoint. Implement as a direct FastAPI route:

```python
# underway/chat/streaming.py

@router.post("/api/chat")
async def chat(request: Request):
    """Main chat endpoint. Returns SSE stream or JSON based on Accept header."""
    ...
```

**SSE Streaming in FastAPI:**

```python
from fastapi.responses import StreamingResponse

async def generate_sse(conversation, messages, model, api_key):
    """Async generator yielding SSE events."""
    async for chunk in litellm.acompletion(..., stream=True):
        # yield SSE events
        ...

return StreamingResponse(
    generate_sse(...),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
)
```

Key difference from Flask: use `litellm.acompletion()` (async) instead of `litellm.completion()`.

### 3.4 Port Tool System

Port `chat/tools.py` with async support:

```python
# underway/chat/tools.py

# TOOL_DEFINITIONS stays the same (it's just a dict)

async def execute_tool(tool_name: str, arguments: dict, user_id: UUID, session: AsyncSession) -> dict:
    """Dispatch tool call to handler."""
    ...

async def _get_tasks(arguments, user_id, session):
    ...

async def _complete_task(arguments, user_id, session):
    ...

async def _create_task(arguments, user_id, session):
    ...

async def _update_task(arguments, user_id, session):
    ...

async def _get_calendar(arguments, user_id, session):
    ...
```

All tool handlers become async and receive a session parameter.

### 3.5 Dashboard Endpoint

Port the dashboard endpoint that returns current tasks + calendar:

```python
@router.get("/api/dashboard")
async def dashboard(request: Request):
    """Return current tasks and calendar state for the chat sidebar."""
    ...
```

### 3.6 SSE Event Protocol

Maintain the same SSE event types for frontend compatibility:

| Event Type | Payload | Purpose |
|-----------|---------|---------|
| `token` | `{type: "token", content: "..."}` | Streamed text token |
| `tool_call` | `{type: "tool_call", name: "...", result: {...}}` | Tool execution result |
| `dashboard_refresh` | `{type: "dashboard_refresh"}` | Signal UI to refresh task/calendar data |
| `done` | `{type: "done", conversation_id: "..."}` | Stream complete |
| `error` | `{type: "error", message: "..."}` | Error occurred |

### 3.7 Vue Frontend — Chat

`frontend/src/views/ChatView.vue`:
- Split layout: chat area (main) + task/calendar sidebar (dashboard)
- Message list with user/assistant message bubbles
- Input field with send button
- SSE streaming: tokens appear progressively
- Tool call results shown inline
- Conversation list in sidebar/drawer
- New conversation button

`frontend/src/components/ChatMessage.vue`:
- Renders markdown content
- Shows tool call results in collapsible sections

`frontend/src/stores/chat.ts` (Pinia):
- `conversations`, `currentConversation`, `messages` state
- `sendMessage()` — handles SSE connection via EventSource or fetch + ReadableStream
- `loadConversations()`, `loadMessages()`, `newConversation()`

`frontend/src/api/chat.ts`:
- `sendMessage(message, conversationId)` — POST with SSE handling
- `getConversations()`, `getMessages(conversationId)`
- `getDashboard()` — for sidebar data

### 3.8 API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/conversations` | List user's conversations |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations/{pk}` | Get conversation |
| DELETE | `/api/conversations/{pk}` | Delete conversation |
| GET | `/api/conversations/{pk}/messages` | Get message history |
| POST | `/api/chat` | Send message (SSE or JSON response) |
| GET | `/api/dashboard` | Current tasks + calendar for sidebar |

### 3.9 Tests

**Unit tests:**
- Tool execution (mock DB): get_tasks, complete_task, create_task, update_task
- Message building (system prompt + history + user message)
- SSE event formatting

**Integration tests:**
- `POST /api/chat` with mocked LLM returns proper response
- `POST /api/chat` with `Accept: text/event-stream` returns SSE
- Tool calling loop: LLM requests tool → tool executes → LLM responds
- Conversation CRUD endpoints
- Messages persisted correctly (user + assistant + tool messages)
- Dashboard returns task/calendar data

**E2E tests (Playwright):**
- Chat page loads with input field
- Send a message, see assistant response appear (mock LLM in test env)
- Conversation appears in sidebar
- New conversation button works
- Dashboard sidebar shows tasks

## Acceptance Criteria

- [ ] Chat endpoint accepts messages and returns LLM responses
- [ ] SSE streaming works with progressive token display
- [ ] Tool calling loop works (LLM → tool → LLM)
- [ ] Conversations persist with full message history
- [ ] Dashboard endpoint returns tasks + calendar data
- [ ] Vue chat page fully functional with streaming
- [ ] All tests pass
