"""SSE streaming chat endpoint and dashboard endpoint."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Annotated, Any

import litellm

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aligned.auth.dependencies import get_current_user, get_db_session
from aligned.auth.jwt import JWTUser
from aligned.chat.tools import MUTATING_TOOLS, TOOL_DEFINITIONS, execute_tool
from aligned.models.conversation import ChatMessage, Conversation
from aligned.models.task import Task
from aligned.models.user import User

router = APIRouter(prefix="/api", tags=["chat"])

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[JWTUser, Depends(get_current_user)]

SYSTEM_PROMPT = (
    "You are Aligned, a task management assistant. You help users:\n"
    "- Break down complex tasks into smaller, actionable subtasks\n"
    "- Track progress by marking tasks complete\n"
    "- Prioritize and reorder their task list\n"
    "- Plan their day using their calendar and tasks\n\n"
    "Be concise and action-oriented. When a user mentions completing something, "
    "use the complete_task tool. When they want to add something, use create_task. "
    "Proactively suggest breaking down large tasks."
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def _build_messages(
    system_prompt: str,
    ai_instructions: str | None,
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the messages list for the LLM call."""
    prompt = system_prompt
    if ai_instructions:
        prompt += f"\n\nAdditional instructions: {ai_instructions}"

    messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}]
    messages.extend(history)
    return messages


def _sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _prepare_and_stream(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    message: str,
    conversation_id: str | None,
) -> AsyncGenerator[str, None]:
    """Set up conversation and stream LLM response.

    Runs entirely in its own DB session so it works in Starlette's
    BaseHTTPMiddleware background task (different greenlet context).
    """
    async with session_factory() as session:
        try:
            # Load user
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user is None:
                yield _sse_event({"type": "error", "message": "User not found"})
                return
            if not user.ai_api_key:
                yield _sse_event({"type": "error", "message": "AI API key not configured"})
                return

            ai_api_key = user.ai_api_key
            llm_model = user.llm_model or "gpt-4o"
            ai_instructions = user.ai_instructions

            # Get or create conversation
            if conversation_id:
                parsed_id = uuid.UUID(conversation_id)
                conv_result = await session.execute(
                    select(Conversation).where(Conversation.id == parsed_id, Conversation.user_id == user_id)
                )
                conversation = conv_result.scalar_one_or_none()
                if conversation is None:
                    yield _sse_event({"type": "error", "message": "Conversation not found"})
                    return
            else:
                conversation = Conversation(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    title=message[:100],
                )
                session.add(conversation)
                await session.flush()

            conv_id = conversation.id

            # Explicitly query messages instead of using the relationship
            # to avoid greenlet issues with selectin loading in background tasks.
            msg_result = await session.execute(
                select(ChatMessage).where(ChatMessage.conversation_id == conv_id).order_by(ChatMessage.sequence)
            )
            existing_messages = list(msg_result.scalars().all())
            next_seq = len(existing_messages)

            # Save user message
            user_msg = ChatMessage(
                id=uuid.uuid4(),
                conversation_id=conv_id,
                role="user",
                content=message,
                sequence=next_seq,
            )
            session.add(user_msg)
            await session.flush()
            next_seq += 1

            # Build message list from plain dicts
            history_dicts = [msg.to_dict() for msg in existing_messages]
            history_dicts.append({"role": "user", "content": message})
            messages = _build_messages(SYSTEM_PROMPT, ai_instructions, history_dicts)

            # Streaming LLM loop
            seq = next_seq
            while True:
                response = litellm.acompletion(
                    model=llm_model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    stream=True,
                    api_key=ai_api_key,
                )

                content_parts: list[str] = []
                tool_calls_by_index: dict[int, dict[str, Any]] = {}

                async for chunk in await response:
                    delta = chunk.choices[0].delta

                    if delta.content:
                        content_parts.append(delta.content)
                        yield _sse_event({"type": "token", "content": delta.content})

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_by_index:
                                tool_calls_by_index[idx] = {
                                    "id": tc.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            entry = tool_calls_by_index[idx]
                            if tc.id:
                                entry["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    entry["function"]["name"] += tc.function.name
                                if tc.function.arguments:
                                    entry["function"]["arguments"] += tc.function.arguments

                if tool_calls_by_index:
                    tool_calls_list = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index)]

                    assistant_content = "".join(content_parts) or None
                    assistant_msg = ChatMessage(
                        id=uuid.uuid4(),
                        conversation_id=conv_id,
                        role="assistant",
                        content=assistant_content,
                        tool_calls=tool_calls_list,
                        sequence=seq,
                    )
                    session.add(assistant_msg)
                    await session.flush()
                    seq += 1

                    messages.append(
                        {
                            "role": "assistant",
                            "content": assistant_content or "",
                            "tool_calls": tool_calls_list,
                        }
                    )

                    for tc in tool_calls_list:
                        func_name = tc["function"]["name"]
                        try:
                            arguments = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}

                        tool_result = await execute_tool(func_name, arguments, user_id, session)

                        yield _sse_event(
                            {
                                "type": "tool_call",
                                "name": func_name,
                                "result": tool_result,
                            }
                        )

                        if func_name in MUTATING_TOOLS:
                            yield _sse_event({"type": "dashboard_refresh"})

                        tool_msg = ChatMessage(
                            id=uuid.uuid4(),
                            conversation_id=conv_id,
                            role="tool",
                            content=json.dumps(tool_result),
                            tool_call_id=tc["id"],
                            sequence=seq,
                        )
                        session.add(tool_msg)
                        await session.flush()
                        seq += 1

                        messages.append(
                            {
                                "role": "tool",
                                "content": json.dumps(tool_result),
                                "tool_call_id": tc["id"],
                            }
                        )

                    continue

                # No tool calls — save assistant message and finish
                full_content = "".join(content_parts)
                assistant_msg = ChatMessage(
                    id=uuid.uuid4(),
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_content,
                    sequence=seq,
                )
                session.add(assistant_msg)
                await session.flush()
                await session.commit()

                yield _sse_event({"type": "done", "conversation_id": str(conv_id)})
                break
        except Exception as exc:
            await session.rollback()
            yield _sse_event({"type": "error", "message": str(exc)})


@router.post("/chat")
async def chat(
    body: ChatRequest,
    current_user: CurrentUser,
    request: Request,
) -> StreamingResponse:
    """SSE streaming chat endpoint with agentic tool-calling loop.

    All DB work runs in the streaming generator's own session to avoid
    greenlet conflicts with Starlette's BaseHTTPMiddleware.
    """
    if not body.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    factory: async_sessionmaker[AsyncSession] = request.state.session_factory

    # Pre-validate API key (quick check, separate session)
    async with factory() as check_session:
        result = await check_session.execute(select(User).where(User.id == current_user.id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if not user.ai_api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI API key not configured",
            )

    return StreamingResponse(
        _prepare_and_stream(
            session_factory=factory,
            user_id=current_user.id,
            message=body.message,
            conversation_id=body.conversation_id,
        ),
        media_type="text/event-stream",
    )


@router.get("/dashboard")
async def dashboard(
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Return tasks (grouped by list) and calendar events (stub)."""
    prioritized, unprioritized, completed = await Task.get_user_tasks_by_list(session, current_user.id)

    return {
        "tasks": {
            "prioritized": [t.to_dict() for t in prioritized],
            "unprioritized": [t.to_dict() for t in unprioritized],
            "completed": [t.to_dict() for t in completed[:10]],
        },
        "events": [],
    }
