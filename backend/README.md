# Backend

The Python part of the project. For each message it:

1. **Classifies** it with an LLM and validates the result with Pydantic (Week 1)
2. **Writes an answer** with a second LLM call (Week 2)
3. **Remembers** the conversation in a SQLite database (Week 3)

All commands below are run from the `backend` folder with the virtual environment active (your prompt shows `(.venv)`).

## Setup (one time)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Your `.env` should contain:

```env
GROQ_API_KEY=gsk_your_real_key_here
GROQ_MODEL=openai/gpt-oss-120b
# Optional: where to store chat history (default: data/chat.db)
# SQLITE_PATH=data/chat.db
```

- No quotes and no spaces around `=`.
- Save it as `.env`, not `.env.txt`.
- Never share it or push it to GitHub (it's already in `.gitignore`).

If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

`--reload` restarts the server automatically when you save a Python file. On startup the server creates `data/chat.db` and its tables if they don't exist.

| Open this | What you get |
|---|---|
| http://127.0.0.1:8000/docs | Interactive page to try every endpoint |
| http://127.0.0.1:8000/health | `{"status":"ok",...,"database":"sqlite"}` |
| http://127.0.0.1:8000/api/conversations | Your saved conversations |
| http://127.0.0.1:8000/ | `{"detail":"Not Found"}`. This is normal; there is no `/` route. |

Stop the server with `Ctrl + C`.

## How the code works, file by file

Read them in this order; each builds on the one before.

### 1. `app/config.py`: settings

Loads `GROQ_API_KEY`, `GROQ_MODEL` and `SQLITE_PATH` from your `.env` file. A relative `SQLITE_PATH` is resolved from the `backend` folder, so the database lands in the same place no matter where you start the server.

### 2. `app/schemas/ingestion.py`: Week 1 data rules

Defines what valid data looks like, using Pydantic:

- **`IngestionRequest`**: what the frontend sends.
  - `message`: 1–5000 characters, trimmed; whitespace-only is rejected.
  - `session_id` (optional): which conversation this message belongs to. Leave it out to start a new one.
- **`IngestionResult`**: what the LLM must return. Only these values are allowed:

| Field | Allowed values |
|---|---|
| `intent` | `greeting`, `order_tracking`, `payment_issue`, `current_time`, `general_question`, `unknown` |
| `risk_profile` | `low`, `medium`, `high`, `unknown` |
| `priority` | `low`, `medium`, `high` |
| `requires_action` | `true` / `false` |
| `summary` | text, 1–500 characters |

`Literal[...]` is what restricts a field to a fixed list. `extra="forbid"` rejects any field we didn't define.

### 3. `app/services/llm_service.py`: Week 1, classify the message

- A **system prompt** tells the LLM what each intent and risk level means.
- **Instructor** wraps the Groq client so the reply must fit `IngestionResult`.
- `temperature=0` gives consistent answers; `max_retries=2` lets Instructor ask again if the reply fails validation.

### 4. `app/utils/token_counter.py`: estimate tokens

Counts roughly how many tokens the message is, using `tiktoken`. It's an estimate only, not Groq's real billing number.

### 5. `app/schemas/assistant.py`: Week 2 data rules

**`AssistantResult`** = everything in `IngestionResult` **plus**:

- `response_markdown`: the written answer
- `session_id`: the conversation id (new or existing)

It inherits from `IngestionResult`, so we don't repeat the fields.

### 6. `app/services/database_service.py`: Week 3, chat history in SQLite

Uses Python's built-in `sqlite3` module, so there is nothing extra to install and no database server to run. Two tables (see `sql/schema.sql`):

| Table | Columns |
|---|---|
| `conversations` | `id` (the session id), `title`, `created_at`, `updated_at` |
| `messages` | `id`, `conversation_id`, `role` (`user`/`assistant`), `content`, `created_at` |

| Function | What it does |
|---|---|
| `initialize_database()` | Creates the file and tables on startup |
| `ensure_conversation(id, title)` | Creates the conversation row if it's new |
| `add_chat_message(id, role, content)` | Saves one message; the first user message becomes the title |
| `get_chat_history(id)` | Last **12** messages, oldest first: the memory sent to the LLM |
| `list_conversations()` | Newest conversations first, for the sidebar |
| `get_conversation_messages(id)` | Every message in one conversation, for reopening a chat |

Every query uses `?` placeholders, never string formatting, which protects against SQL injection.

### 7. `app/services/response_service.py`: Week 2, write the answer

- Takes the **validated** Week 1 result, the **recent history** and the **current message**.
- Sends them to the LLM with a support-assistant prompt: be clear, use earlier messages to understand follow-ups like "that order", never ask for passwords/OTPs, don't pretend to take actions.
- Returns the answer as Markdown. `temperature=0.3` lets the wording vary a little so it sounds natural.

### 8. `app/main.py`: the API

Connects everything:

```text
POST /api/analyze
  → IngestionRequest checks the message (and session_id, if sent)
  → no session_id? create a new one
  → analyze_message()        (Week 1)
  → estimate_tokens()
  → get_chat_history()       (Week 3)
  → generate_response()      (Week 2, with history)
  → add_chat_message() ×2    (Week 3: save user + assistant messages)
  → returns AssistantResult
```

Any error in the LLM calls becomes HTTP `502`.

## API reference

### `POST /api/analyze`

Start a new conversation (no `session_id`):

```json
{ "message": "Where is my order?" }
```

Continue it (send back the `session_id` you received):

```json
{ "message": "It was placed last Monday", "session_id": "c2e10ce1-98c4-4e7a-9d7d-be6712af88f3" }
```

Response (wording varies):

```json
{
  "intent": "order_tracking",
  "risk_profile": "medium",
  "priority": "medium",
  "requires_action": true,
  "summary": "User is asking about the status of their order.",
  "token_metadata": { "estimated_input_tokens": 5, "note": "Estimated locally; may differ from provider token counts." },
  "session_id": "c2e10ce1-98c4-4e7a-9d7d-be6712af88f3",
  "response_markdown": "## Tracking your order\n\n- Check the confirmation email...\n"
}
```

### `GET /api/conversations`

The 30 most recent conversations:

```json
{ "items": [ { "session_id": "c2e1…", "title": "Where is my order?", "updated_at": "2026-10-24T07:30:12+00:00", "preview": "It was placed last Monday" } ] }
```

### `GET /api/conversations/{session_id}/messages`

Every message in one conversation, oldest first:

```json
{ "session_id": "c2e1…", "items": [ { "role": "user", "content": "Where is my order?", "created_at": "…" } ] }
```

### `GET /health`

Returns `{"status": "ok", "message": "...", "database": "sqlite"}`. Doesn't call the LLM, so it's a quick way to check the server is up.

| Status code | Meaning |
|---|---|
| `200` | Success |
| `400` | The conversation id in the URL isn't a valid UUID |
| `422` | Bad input (empty message, too long, invalid `session_id`, or extra fields) |
| `502` | The LLM call failed (see troubleshooting) |

Try it from PowerShell without the frontend:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/analyze `
  -ContentType "application/json" `
  -Body '{"message":"Where is my order?"}'
```

## Looking inside the database

The file is `backend/data/chat.db`.

- **VS Code:** install the **SQLite Viewer** extension and click the file.
- **Terminal** (works while the server is running):

  ```powershell
  python -c "import sqlite3; c=sqlite3.connect('data/chat.db'); [print(r) for r in c.execute('SELECT conversation_id, role, substr(content,1,60) FROM messages ORDER BY id')]"
  ```

- **Start fresh:** stop the server and delete the `data` folder.

## Tests

```powershell
pytest -q
```

Expected: `8 passed`.

| File | Checks |
|---|---|
| `tests/test_ingestion.py` | Week 1 Pydantic rules (trimming, blank messages, invalid intent, valid data) |
| `tests/test_database.py` | Week 3 SQLite storage (order of messages, 12-message limit, titles, invalid roles) using a temporary database |

None of them call the LLM, so they work without an API key or internet.

## Troubleshooting

### `502 The AI request failed`

The API hides the real reason, so call the Week 1 service directly to see it:

```powershell
python -c "from app.services.llm_service import analyze_message; print(analyze_message('Hi'))"
```

The server terminal also prints the error after `Request failed for session ...`.

| Error you see | Meaning | Fix |
|---|---|---|
| `401` / invalid API key | Key is wrong or expired | Fix `GROQ_API_KEY` in `.env` |
| `404 model_not_found` | That model doesn't exist anymore | Pick one from the list below and set `GROQ_MODEL` |
| `GROQ_API_KEY is missing` | `.env` not found | Make sure the file is `backend\.env`, not `.env.txt` |
| Connection / timeout | No internet or Groq is down | Check your connection |
| `database is locked` | Something else has the database open for writing | Close other programs using `chat.db` |

List the models your key can use:

```powershell
python -c "from groq import Groq; from app.config import GROQ_API_KEY; [print(m.id) for m in Groq(api_key=GROQ_API_KEY).models.list().data]"
```

Restart `uvicorn` after changing `.env`.

### Port 8000 already in use

An old server is still running. Press `Ctrl + C` in its terminal, or check what's using the port:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

## Known limitations (good discussion topics)

- If Instructor runs out of retries, it raises `InstructorRetryException`, not `ValidationError`, so you get the generic 502 instead of the detailed validation message.
- The conversation row is created before the LLM is called, so a failed request can leave an empty conversation in the sidebar.
- `token_metadata` is part of the schema sent to the LLM in Week 1, so the model may fill it in; the code overwrites the count afterwards.
- A new Groq client and a new SQLite connection are created on every request. Simple, but not the fastest.
- There are no user accounts: anyone who can reach the API can read every conversation.
- CORS allows every website (`*`). Fine for learning, but restrict it before deploying.
- `app/services/conversation_service.py` is the old in-memory history from early Week 3 and is no longer used.