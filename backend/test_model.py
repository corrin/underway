"""Quick smoke-test for any LiteLLM-supported model.

Usage:
    python test_model.py <model> <api_key>

Examples:
    python test_model.py moonshot/kimi-k2-turbo-preview sk-...
    python test_model.py gpt-4o-mini sk-...
    python test_model.py claude-3-5-haiku-20241022 sk-ant-...
"""

import asyncio
import sys


async def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python test_model.py <model> <api_key>")
        sys.exit(1)

    model, api_key = sys.argv[1], sys.argv[2]
    print(f"Testing model: {model}")
    print("Sending: 'Reply with exactly: OK'")
    print("-" * 40)

    import litellm

    # 1. Basic completion
    response = await litellm.acompletion(
        model=model,
        api_key=api_key,
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
    print(f"✓ Basic completion: {response.choices[0].message.content!r}")

    # 2. Streaming
    chunks = []
    stream = await litellm.acompletion(
        model=model,
        api_key=api_key,
        messages=[{"role": "user", "content": "Count to 3, one number per line."}],
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
    print(f"✓ Streaming:        {''.join(chunks)!r}")

    # 3. Tool calling
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    tool_response = await litellm.acompletion(
        model=model,
        api_key=api_key,
        messages=[{"role": "user", "content": "What's the weather in Auckland?"}],
        tools=tools,
    )
    tool_calls = tool_response.choices[0].message.tool_calls
    if tool_calls:
        print(f"✓ Tool calling:     called {tool_calls[0].function.name!r} with {tool_calls[0].function.arguments}")
    else:
        print("✗ Tool calling:     no tool call made (model may not support it)")

    print("-" * 40)
    print("All tests passed.")


asyncio.run(main())
