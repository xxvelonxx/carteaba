# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Running

```bash
# Full automated setup (installs Ollama, models, Python deps):
bash setup.sh

# Manual setup:
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors langchain langchain-community langchain-ollama chromadb pypdf requests tweepy python-telegram-bot

# Start server:
python3 server.py
# Dashboard: http://localhost:7777/dashboard
```

Requires Ollama running separately (`ollama serve`). Default model: `dolphin-llama3:8b`. Embedding model `nomic-embed-text` must also be pulled.

## Running Tests

```bash
# From the project root with venv activated:
python -m pytest test_knowledge_memory.py test_taboo_manager.py test_telegram_handler.py -v

# Single test file:
python -m pytest test_knowledge_memory.py -v

# Single test:
python -m pytest test_knowledge_memory.py::TestKnowledgeMemory::test_add_core_belief -v
```

Tests use `unittest` discovered via pytest. `test_taboo_manager.py` imports `TabooManager` directly from `server.py`.

## Architecture

**Entry point:** `server.py` — Flask app, all API routes, and the `TabooManager` + `ConversationMemory` classes inline.

**Data flow for chat:**
1. `POST /api/chat` or `/api/chat/stream` receives `{query, conv_id, use_rag}`
2. RAG retrieval via ChromaDB (`langchain_community.vectorstores.Chroma`)
3. `build_personality_prompt()` assembles the final prompt from: active personality system prompt → optional uncensored boost → active taboos → knowledge memory context → doc context → conversation history
4. `OllamaLLM.invoke()` / `.stream()` generates the response

**Persistence layer** — all state lives in these directories (created at startup):
- `uploads/` — raw PDFs
- `chromadb_data/` — vector embeddings (ChromaDB)
- `memory/` — `conversations.json`, `taboos.json`, `knowledge_memory.json.gz`, `documents.json`
- `twitter_data/tweet_history.json`
- `telegram_data/message_history.json`, `user_memories.json.gz`

**Module responsibilities:**
- `knowledge_memory.py` — `KnowledgeMemory`: extracts insights/arguments from PDF chunks, compresses when exceeding size limits, formats context for prompts. All knowledge stored in `memory/knowledge_memory.json.gz`.
- `telegram_handler.py` — `TelegramHandler` + `UserMemory`: polls Telegram via `python-telegram-bot`, maintains per-user persistent memory in gzip JSON, responds automatically using the active personality.
- `twitter_handler.py` — `TwitterHandler`: searches tweets via Tweepy v2 API, generates replies using active personality, optionally auto-posts. Scans on configurable interval in background thread.

**Config:** `config.json` is the single source of truth. Loaded at startup into the global `CONFIG` dict. `PUT /api/config` mutates `CONFIG` and writes back to disk. The `personalities` dict inside config drives the prompt assembly; `active_personality` selects which one is used.

**Lazy-loaded singletons:** `_llm`, `_vectorstore`, `_embeddings`, `_twitter_handler`, `_telegram_handler`, `_knowledge_memory`, `_taboo_manager` — all initialized on first use via `get_*()` helpers. Changing `model`/`temperature`/`num_ctx` via the config API sets `_llm = None` to force re-initialization.
