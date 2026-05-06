"""Prompt loader.

Each prompt lives in `app/llm/prompts/<name>.md`. Loaders strip the metadata header
(everything before the first `---` divider) and return the body as a Python string
template that can be `.format(...)`-ed by the calling service.

Convention for prompt files:

    # Prompt: <name>
    # version: N
    # changelog:
    # - vN: ...
    ---
    <prompt body, possibly with {placeholders}>
"""

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load `<name>.md` from the prompts directory and return the body."""
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    text = path.read_text(encoding="utf-8")
    if "---" in text:
        # Split on the first --- divider; everything after is the prompt body
        _, _, body = text.partition("\n---\n")
        return body.strip()
    return text.strip()
