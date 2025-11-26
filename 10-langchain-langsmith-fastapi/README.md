# FastAPI + LangChain Chat Demo

This repository implements a single FastAPI application that integrates:

- A `/chat` endpoint with basic validation and mocked auth.
- LangChain + OpenAI for LLM responses (single-turn with optional memory).
- Tone control (`friendly`, `formal`, `cheerful`, `concise`).
- Per-user DB context (tasks) injected into the prompt.
- Structured output via `with_structured_output(...)`, including a boolean
  `used_context` flag.
- Optional LangSmith tracing via environment variables.

## 1. Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 2. Configuration

Copy `.env.example` to `.env` and fill in your OpenAI key:

```bash
cp .env.example .env
# Edit .env -> set OPENAI_API_KEY and, optionally, OPENAI_MODEL
```

The app reads:

- `OPENAI_API_KEY` – required for OpenAI / LangChain.
- `OPENAI_MODEL` – defaults to `gpt-4o-mini`.
- `LANGSMITH_TRACING` – if `true`, the app will also set `LANGCHAIN_TRACING_V2=true`
  so LangSmith tracing is enabled (you must still export `LANGCHAIN_API_KEY` and
  optionally `LANGCHAIN_PROJECT` yourself).

## 3. Running the app

```bash
uvicorn app.main:app --reload
```

By default this starts the API on http://127.0.0.1:8000.

Open the interactive docs at http://127.0.0.1:8000/docs to test `/chat`.

## 4. `/chat` Endpoint

**Method:** `POST /chat`  
**Request body:**

```json
{
  "message": "What are my tasks?",
  "tone": "friendly"
}
```

- `message` – required, non-empty string. Empty/whitespace -> `400` error.
- `tone` – optional, one of: `friendly`, `formal`, `cheerful`, `concise`
  (case-insensitive). Invalid value -> `400` error. Default is `friendly`.

**Response (200):**

```json
{
  "answer": "Hi Demo User, here is a summary of your current tasks ..."
}
```

Internally, the LLM is invoked via LangChain with a structured output model:

```python
class StructuredChatResponse(BaseModel):
    answer: str
    used_context: bool
```

- `answer` is returned to the client.
- `used_context` is used only internally to track whether the LLM clearly
  relied on DB context (tasks) for its reply.

**Error examples:**

- Empty message:

  ```json
  HTTP 400
  { "detail": "Message must not be empty or whitespace." }
  ```

- Invalid tone:

  ```json
  HTTP 400
  { "detail": "Invalid tone 'angry'. Allowed values: cheerful, concise, formal, friendly." }
  ```

- LLM error (e.g., network issue):

  ```json
  HTTP 500
  { "detail": "LLM backend error while processing your request." }
  ```

## 5. DB Context

A single demo user is used to mock authentication:

- Email: `demo.user@example.com`
- Name: `Demo User`

On startup the app:

- Creates the SQLite database `chat_app.db`.
- Seeds the demo user.
- Seeds a few tasks for that user.

The top 3 most recent tasks for the demo user are collected, formatted as
plain text, and injected into the prompt as context. Queries like:

```json
{ "message": "What are my tasks?", "tone": "friendly" }
```

will cause the LLM to read this context and describe these tasks. The model
is instructed to set `used_context = true` when it relies on these tasks for
the answer, otherwise `false`.

## 6. Conversation Memory (Bonus Part 5)

The app stores each turn in the `chat_messages` table:

- User messages (`role="user"`)
- Assistant messages (`role="assistant"`)

For each new `/chat` call, the API:

1. Fetches up to the last 10 messages for the current user.
2. Converts them to LangChain `HumanMessage` / `AIMessage` objects.
3. Feeds them into the chain via `MessagesPlaceholder("history")`.

This provides a simple windowed memory over the last 10 messages. Once there
are more than 10 messages, the oldest ones are no longer included in the
LLM call.

## 7. LangSmith Tracing (Part 6)

To enable LangSmith tracing:

1. Export an API key and (optionally) project name:

   ```bash
   export LANGCHAIN_API_KEY=your-langsmith-api-key
   export LANGCHAIN_PROJECT=fastapi-langchain-chat-demo
   ```

2. Set `LANGSMITH_TRACING=true` (or set `LANGCHAIN_TRACING_V2=true` yourself):

   ```bash
   export LANGSMITH_TRACING=true
   ```

When the app starts, it will:

- Detect `LANGSMITH_TRACING=true`
- Set `LANGCHAIN_TRACING_V2=true`

From there, LangChain / LangSmith will automatically send traces for every
call to the `ChatOpenAI` model, including:

- Prompt variables (`user_name`, `tone`, `user_context`, `user_message`)
- Rendered prompt messages (system, history, human)
- Structured output (`answer`, `used_context`)

You can open the LangSmith UI to inspect and share those traces.

## 8. Notes

- API keys must **never** be committed to a public repository. Keep your
  GitHub repo private and use a local `.env` file or CI secrets.
- The SQLite database `chat_app.db` is stored in the project root by default;
  you can change `SQLALCHEMY_DATABASE_URL` in `app/database.py` if needed.
- The app is intentionally small and focused on the assignment requirements,
  but it is structured so you can easily extend it with more endpoints and
  entities.
