# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Research Assistant Agent (研究助手 Agent) — a Chinese-language AI agent that automates web research workflows. Users describe research tasks in natural language; the agent searches, analyzes, and saves results automatically.

**Current status:** Early MVP with skeleton code. Uses Zhipu AI's GLM-4.7-Flash model via OpenAI-compatible API.

## Environment Setup

**Virtual environment:**
```bash
source venv/bin/activate
```

**Environment variables** (set in `.env` file, which is git-ignored):
```bash
ZHIPU_API_KEY=<your-key>
ZHIPU_BASE_URL='https://open.bigmodel.cn/api/paas/v4/'
```

The `load_dotenv()` call must happen before any `os.getenv()` calls (see `main.py:6`).

## Running and Testing

```bash
# Run the main script (tests LLM connectivity + web_search tool)
python main.py
```

The script performs two tests:
1. **LLM connectivity test** — sends a simple prompt to GLM-4.7-Flash
2. **web_search tool test** — searches "AI Agent 最新发展" via DuckDuckGo (max 3 results)

## Architecture

**Single-file architecture (`main.py`):**

- **LLM client:** Uses `openai` SDK with custom `base_url` to connect to Zhipu AI
- **Tool system:** Manual tool definition (JSON schema) for `web_search` function
- **Search backend:** `duckduckgo_search` library via `DDGS()` context manager

**Key function:**
- `web_search(query, max_results)` — wraps DuckDuckGo search, returns JSON string of results

## Dependencies

Key packages:
- `openai` — LLM API client (used with Zhipu's OpenAI-compatible endpoint)
- `duckduckgo_search` — web search without API keys
- `python-dotenv` — environment variable loading
- `pydantic` — data validation

## Notes

- Codebase is Chinese-first (comments, UI, documentation)
- No tests, linting, or formal build process yet
- `.gitignore` protects `venv/`, `__pycache__/`, and `.env`

## Git Workflow

**NEVER auto-commit.** All git commits require explicit user approval:
1. Show changes/diff to user
2. Ask for confirmation
3. Only commit after user agrees

## Code Modification Workflow

**Propose solution first, then implement.** Never modify code without approval:
1. Analyze the problem
2. Propose a solution (explain what and why)
3. Wait for user confirmation
4. Only then modify code with Edit/Write tools
