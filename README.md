# Indigo.ai

_Enterprise Structured Ingestion Firewall_

A beginner-friendly AI project. You chat with **Indigo.ai**, an AI assistant in a React web app, and for every message the backend:

1. **Week 1 – Understands it.** An LLM sorts the message into a fixed category (payment issue, order tracking, greeting…) and returns structured JSON. Pydantic checks that JSON before anything else uses it.
2. **Week 2 – Answers it.** A second LLM call uses that checked JSON to write a helpful reply in Markdown.
3. **Week 3 – Remembers it.** Every conversation is saved in a **SQLite** database, so follow-up questions ("what about my other order?") make sense and you can reopen old chats.

The "firewall" idea: the AI's output is not trusted until it passes a strict schema. If the model returns a category that doesn't exist or a missing field, the app rejects it.

## What you will learn

- Building an API with **FastAPI**
- Calling a cloud LLM (**Groq**) from Python
- Getting **structured output** from an LLM with **Instructor**
- **Validating** data with **Pydantic**
- Saving chat history in **SQLite** (built into Python, no server needed)
- Building a **React + Vite** frontend and connecting it to an API

## Key words (quick glossary)

| Word | Meaning in this project |
|---|---|
| **LLM** | Large Language Model, the AI that reads and writes text. We use one hosted by Groq. |
| **API** | The backend URLs the frontend calls, e.g. `/api/analyze`. |
| **FastAPI** | The Python library that runs our API. |
| **Pydantic** | Checks that data has the right fields and allowed values. |
| **Instructor** | Makes the LLM reply in a shape that matches our Pydantic model. |
| **Schema** | The rules for what valid data looks like. |
| **Intent** | What the user wants, e.g. `payment_issue`. |
| **Session ID** | A unique ID for one conversation, so the backend knows which history to use. |
| **SQLite** | A database stored in a single file (`backend/data/chat.db`). |
| **React / Vite** | React builds the UI from components; Vite runs it in development and builds it for production. |
| **`.env` file** | A private file holding your API key. Never share or commit it. |
| **venv** | A private Python environment just for this project. |

## How a message flows through the app

```text
 You type in the React app (http://localhost:5173)
        │
        ▼
 POST /api/analyze { message, session_id? } ──► FastAPI backend (port 8000)
                                                  │
     1. Check the input                 schemas/ingestion.py
     2. WEEK 1: classify it             services/llm_service.py      ── LLM call #1
          └─ Pydantic validates the JSON
     3. Estimate tokens                 utils/token_counter.py
     4. WEEK 3: load recent history     services/database_service.py ── SQLite
     5. WEEK 2: write a reply           services/response_service.py ── LLM call #2
     6. WEEK 3: save both messages      services/database_service.py ── SQLite
                                                  │
        ◄──── JSON: intent details + response_markdown + session_id
        │
 The chat shows the answer; the right panel shows intent, risk and priority
```

## What you need

- **Python 3.10 or newer** (check with `python --version`)
- **Node.js 18 or newer** (check with `node --version`): https://nodejs.org
- A free **Groq API key**: https://console.groq.com/keys
- Internet connection

## Run it (Windows PowerShell)

You need **two terminals**: one for the backend, one for the frontend.

### Step 1: Set up the backend (one time only)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

You'll know the venv is active when your prompt starts with `(.venv)`. `requirements-dev.txt` installs the app (`requirements.txt`) plus the test tools; Render only installs `requirements.txt`.

### Step 2: Add your API key (one time only)

```powershell
copy .env.example .env
notepad .env
```

Replace the placeholder key with yours, then save:

```env
GROQ_API_KEY=gsk_your_real_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

No database setup is needed; the SQLite file is created automatically.

### Step 3: Start the backend (Terminal 1)

Still inside `backend`, with `(.venv)` showing:

```powershell
uvicorn app.main:app --reload --port 8000
```

Check it at http://127.0.0.1:8000/health. You should see `"status": "ok"`, `"database_ok": true` and `"groq_api_key_configured": true`. Leave this terminal running.

### Step 4: Start the frontend (Terminal 2)

Open a **new** terminal in the project root:

```powershell
cd frontend-react
npm install        # first time only
npm run dev
```

### Step 5: Open the app

Go to http://localhost:5173 and click **Get Started**. The sidebar dot is green when the backend is connected.

To stop the servers, press `Ctrl + C` in each terminal.

On macOS/Linux, use `source .venv/bin/activate` instead of `Activate.ps1`, and `cp` instead of `copy`.

## Where is my chat history?

In `backend/data/chat.db`, created the first time the backend starts. Ways to look at it:

- In the browser: http://127.0.0.1:8000/api/conversations
- In VS Code: install the **SQLite Viewer** extension and click the file
- To start fresh: stop the backend and delete the `backend/data` folder

The database is in `.gitignore`, so your chats are never pushed to GitHub.

## API endpoints

| Method | Path | What it does |
|---|---|---|
| `GET` | `/` | Simple status: `{"service": "Indigo.ai API", "status": "running"}` |
| `GET` | `/health` | Server status: `database_ok`, `groq_api_key_configured`, `model`. Never calls the LLM or shows secrets. |
| `GET` | `/docs` | Interactive documentation: try every endpoint in the browser |
| `POST` | `/api/analyze` | Send `{ "message": "...", "session_id": "optional" }`; returns intent, risk, priority, the Markdown answer and `session_id` |
| `GET` | `/api/conversations` | The 30 most recent conversations |
| `POST` | `/api/analyze/stream` | Same as above, but the answer streams in piece by piece (used by the app). Add `"incognito": true` to save nothing. Ends with input/output token counts. |
| `GET` | `/api/conversations/{session_id}/messages` | Every message in one conversation |
| `PATCH` | `/api/conversations/{session_id}` | Rename a conversation: `{ "title": "..." }` |
| `POST` | `/api/conversations/{session_id}/archive` | Move a conversation to the archive (kept 30 days) |
| `POST` | `/api/conversations/{session_id}/restore` | Bring an archived conversation back |
| `GET` | `/api/conversations/archived` | Archived conversations with their deletion dates |
| `DELETE` | `/api/conversations/{session_id}` | Delete a conversation and its messages permanently |

Full request/response examples are in [backend/README.md](backend/README.md#api-reference).

## Deploy: backend on Render, frontend on Vercel

Deploy the **backend first**, because the frontend needs its URL.

### Before you start

- [ ] Code is pushed to GitHub, and `git status` shows nothing uncommitted.
- [ ] `backend/.env` is **not** on GitHub. It's in `.gitignore`; check the repo page to be sure.
- [ ] Tests pass: `cd backend` then `pytest -q` (27 passed).
- [ ] Frontend builds: `cd frontend-react` then `npm run build`.
- [ ] You have your Groq API key ready to paste into Render.

### Environment variables

| Where | Name | Value | Required |
|---|---|---|---|
| Render | `GROQ_API_KEY` | Your Groq key (`gsk_...`) | Yes |
| Render | `GROQ_MODEL` | `openai/gpt-oss-120b` | Yes (default is the same) |
| Render | `ALLOWED_ORIGINS` | Your Vercel URL, e.g. `https://your-app.vercel.app` (no trailing slash; comma-separate several) | Yes |
| Render | `PYTHON_VERSION` | `3.12.10` | Yes (set automatically by `render.yaml`) |
| Render | `DATABASE_URL` | Your Neon connection string (`postgresql://…?sslmode=require`) so chats are kept | Yes (recommended) |
| Render | `SQLITE_PATH` | `/var/data/chat.db`, only with a paid persistent disk and no `DATABASE_URL` | No |
| Vercel | `VITE_API_URL` | Your Render URL, e.g. `https://ai-assistant-backend.onrender.com` (no trailing slash) | Yes |

Never put real keys in `.env.example`, the code or the README. Only paste them into the Render/Vercel dashboards.

### Step 1: Backend on Render

**Option A, Blueprint (uses `render.yaml`):** Render → **New** → **Blueprint** → pick this repo. It fills in everything below and asks for `GROQ_API_KEY` and `ALLOWED_ORIGINS`. For now, put `http://localhost:5173` in `ALLOWED_ORIGINS`; you'll update it after Step 2.

**Option B, by hand:** Render → **New** → **Web Service** → pick this repo, then:

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

Add the Render environment variables from the table above.

When the deploy finishes, open `https://<your-service>.onrender.com/health` and check that `database_ok` and `groq_api_key_configured` are both `true`.

### Step 2: Frontend on Vercel

Vercel → **Add New** → **Project** → import this repo, then:

| Setting | Value |
|---|---|
| Root Directory | `frontend-react` |
| Framework Preset | Vite (auto-detected) |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Environment Variable | `VITE_API_URL` = your Render URL |

`frontend-react/vercel.json` sends every path to `index.html`, so links like `/chat/<id>` work after a page refresh.

### Step 3: Connect them

1. Copy your Vercel URL, e.g. `https://your-app.vercel.app`.
2. In Render → your service → **Environment**, set `ALLOWED_ORIGINS` to that URL and save. Render redeploys automatically.
3. Open the Vercel site → **Get Started** → send a message.

If you change `VITE_API_URL` later, **redeploy** on Vercel: Vite bakes it into the build.

### Check the deployment

| Check | Expected |
|---|---|
| `https://<render-url>/` | `{"service": "Indigo.ai API", "status": "running"}` |
| `https://<render-url>/health` | `"status": "ok"`, `"database_ok": true`, `"groq_api_key_configured": true` |
| `https://<render-url>/docs` | Interactive API page |
| `https://<render-url>/api/conversations` | `{"items": [...]}` |
| Vercel site → sidebar dot | Green, "Backend connected" |
| Send a message on the Vercel site | Answer appears; right panel shows the intent |
| Refresh the page on `/chat/<id>` | Same conversation reloads (not a 404) |

### Things to know about the free plans

- **Keep chats with a free Neon database.** Without `DATABASE_URL`, chats are saved in a SQLite file that Render's free plan wipes on every deploy and restart. Create a free PostgreSQL database at [neon.tech](https://neon.tech), copy its connection string and set it as `DATABASE_URL` on Render. Tables are created automatically on first start; you can see them in the Neon console under **Tables**.
- **The free backend sleeps** after about 15 minutes without traffic. The first request afterwards can take up to a minute; the app shows "Backend offline" until it wakes, then try again.
- **The API is public.** There are no user accounts: anyone with the URL can read every saved conversation and use your Groq quota. Fine for a workshop demo; add authentication and rate limiting before real users.

## Common problems

| What you see | Why | Fix |
|---|---|---|
| Red dot / "Backend offline" in the app | Backend isn't running | Do Step 3 |
| `npm` is not recognized | Node.js isn't installed | Install it from https://nodejs.org and reopen the terminal |
| `{"detail":"Not Found"}` at http://127.0.0.1:8000/ | Normal: there is no `/` route | Use `/docs` or `/health` |
| `502 The AI request failed` | Wrong key, or the model name doesn't exist | See [backend/README.md](backend/README.md#troubleshooting) |
| `Activate.ps1 cannot be loaded` | PowerShell blocks scripts | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Port already in use | An old server is still running | Press `Ctrl + C` in its terminal, then start again |
| Deployed site: "Cannot reach the backend" | Render is waking up, or `ALLOWED_ORIGINS` doesn't include the Vercel URL | Wait a minute and retry; check `ALLOWED_ORIGINS` matches the Vercel URL exactly |
| Deployed site: "unexpected response… VITE_API_URL" | `VITE_API_URL` isn't set on Vercel | Set it, then redeploy |
| Deployed site: 404 when refreshing `/chat/...` | Vercel root directory isn't `frontend-react` (so `vercel.json` is ignored) | Set Root Directory to `frontend-react` |
| Render `/health` shows `groq_api_key_configured: false` | Key not set on Render | Add `GROQ_API_KEY` in Render → Environment |

## Project map

```text
enterprise-ingestion-firewall/
├── backend/                       ← Python API (see backend/README.md)
│   ├── app/
│   │   ├── main.py                ← all API routes
│   │   ├── config.py              ← reads your .env file
│   │   ├── schemas/
│   │   │   ├── ingestion.py       ← Week 1 data rules (input + intent result)
│   │   │   └── assistant.py       ← Week 2 data rules (adds answer + session_id)
│   │   ├── services/
│   │   │   ├── llm_service.py     ← Week 1: classify the message
│   │   │   ├── response_service.py← Week 2: write the answer
│   │   │   └── database_service.py← Week 3: save/load chats in SQLite
│   │   └── utils/token_counter.py ← estimates token count
│   ├── sql/schema.sql             ← the database tables (reference)
│   ├── tests/                     ← pytest tests
│   ├── .env.example               ← copy this to .env
│   ├── .python-version            ← Python version for Render
│   ├── requirements.txt           ← app packages (installed on Render)
│   └── requirements-dev.txt       ← app + test packages (local)
├── frontend-react/                ← React + Vite app (see frontend-react/README.md)
│   ├── .env.example               ← VITE_API_URL for deployment
│   └── vercel.json                ← Vercel settings + page routing
├── render.yaml                    ← Render Blueprint for the backend
└── README.md                      ← you are here
```

## Good to know

- Each message makes **two** LLM calls (classify, then answer).
- The assistant uses the **last 12 messages** of a conversation as memory.
- The app does **not** really look up orders or reset passwords; it only classifies and gives advice.
- Token counts are **estimates**, not what Groq bills.
- Schema validation checks the **shape** of data, not whether the AI's answer is true.

## Next reading

- [backend/README.md](backend/README.md): each Python file, the API, the database, tests, troubleshooting
- [frontend-react/README.md](frontend-react/README.md): how the React app is organized and connects to the API