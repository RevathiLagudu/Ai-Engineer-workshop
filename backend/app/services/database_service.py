
"""Supabase repository for conversations and messages."""

import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

MAX_HISTORY_MESSAGES = 12

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()


def _client():
    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SECRET_KEY in backend/.env"
        )
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_database() -> None:
    """Check that Supabase tables are accessible."""
    db = _client()
    db.table("conversations").select("id").limit(1).execute()
    db.table("messages").select("id").limit(1).execute()


def ensure_conversation(
    session_id: str, title: str = "New Chat"
) -> None:
    db = _client()

    existing = (
        db.table("conversations")
        .select("id")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        db.table("conversations").insert({
            "id": session_id,
            "title": (title[:100] or "New Chat"),
            "created_at": _now(),
            "updated_at": _now(),
        }).execute()


def add_chat_message(
    session_id: str, role: str, content: str
) -> None:
    if role not in ("user", "assistant"):
        raise ValueError("role must be 'user' or 'assistant'")

    ensure_conversation(
        session_id,
        content[:70] if role == "user" else "New Chat",
    )

    db = _client()
    now = _now()

    # Insert the message into Supabase.
    db.table("messages").insert({
        "conversation_id": session_id,
        "role": role,
        "content": content,
        "created_at": now,
    }).execute()

    # Update the conversation timestamp and its initial title.
    conversation = (
        db.table("conversations")
        .select("title")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )

    updates = {"updated_at": now}
    if (
        role == "user"
        and conversation.data
        and conversation.data[0]["title"] == "New Chat"
    ):
        updates["title"] = content[:70] or "New Chat"

    db.table("conversations").update(updates).eq(
        "id", session_id
    ).execute()


def get_chat_history(session_id: str) -> list[dict[str, str]]:
    result = (
        _client()
        .table("messages")
        .select("id,role,content")
        .eq("conversation_id", session_id)
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(MAX_HISTORY_MESSAGES)
        .execute()
    )

    return [
        {"role": row["role"], "content": row["content"]}
        for row in reversed(result.data or [])
    ]


def list_conversations(
    limit: int = 30,
) -> list[dict[str, Any]]:
    db = _client()

    result = (
        db.table("conversations")
        .select("id,title,updated_at")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )

    items = []
    for conversation in result.data or []:
        latest = (
            db.table("messages")
            .select("content")
            .eq("conversation_id", conversation["id"])
            .eq("role", "user")
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        items.append({
            "session_id": conversation["id"],
            "title": conversation["title"],
            "updated_at": conversation["updated_at"],
            "preview": (
                latest.data[0]["content"]
                if latest.data
                else "Start a conversation"
            ),
        })

    return items


def get_conversation_messages(
    session_id: str,
) -> list[dict[str, Any]]:
    result = (
        _client()
        .table("messages")
        .select("role,content,created_at")
        .eq("conversation_id", session_id)
        .order("created_at")
        .order("id")
        .execute()
    )

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
        }
        for row in result.data or []
    ]
