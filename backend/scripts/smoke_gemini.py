"""One-shot smoke test for the Gemini provider.

Hits the real API. Run with:
    uv run python scripts/smoke_gemini.py
"""

import asyncio

from app.llm.base import Message
from app.llm.providers.gemini import GeminiProvider


async def main() -> None:
    provider = GeminiProvider()
    print(f"Provider: {provider.name} / {provider.default_model}")
    result = await provider.complete(
        [Message(role="user", content="Reply with exactly: pong")],
        temperature=0.0,
    )
    print(f"Text: {result.text!r}")
    print(f"Input tokens: {result.input_tokens}, output tokens: {result.output_tokens}")
    assert "pong" in result.text.lower(), f"Unexpected reply: {result.text}"
    print("OK")


if __name__ == "__main__":
    asyncio.run(main())
