"""Simple in-memory conversation history for Week 3 learning.

History is process-local and is cleared when the API restarts. Use a database
such as PostgreSQL/Supabase for persistent storage in a later iteration.
"""
from collections import defaultdict, deque
from threading import RLock
from typing import Any

MAX_HISTORY_MESSAGES = 12  # Keep the most recent six user/assistant exchanges.
_history: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY_MESSAGES)
)
_lock = RLock()


def get_history(session_id: str) -> list[dict[str, str]]:
    """Return a copy so callers cannot mutate the stored history directly."""
    with _lock:
        return list(_history[session_id])


def add_message(session_id: str, role: str, content: str) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("Conversation role must be 'user' or 'assistant'.")
    with _lock:
        _history[session_id].append({"role": role, "content": content})


def clear_session(session_id: str) -> None:
    with _lock:
        _history.pop(session_id, None)


def clear_all_sessions() -> None:
    """Utility for tests and local development only."""
    with _lock:
        _history.clear()