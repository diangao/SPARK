# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

S.P.A.R.K. (System for Proactive Accountability, Rhythm & Knowledge) — A Telegram Bot powered by Claude Agent that proactively checks in, reminds, and helps maintain rhythm. It integrates with Think OS (a local markdown-based knowledge system) for real-time read/write access.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  Telegram   │────▶│  Bot Server │────▶│   Claude Agent   │
│   (User)    │◀────│  (Python)   │◀────│  (Agent SDK)     │
└─────────────┘     └─────────────┘     └──────────────────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────┐      ┌─────────────┐
                    │  Scheduler  │      │  Think OS   │
                    │ (APScheduler)│      │ (markdown)  │
                    └─────────────┘      └─────────────┘
```

## Tech Stack

- Python 3.11+
- `anthropic` — Claude API
- `python-telegram-bot` — Telegram integration
- `APScheduler` — Scheduled tasks

## Commands

```bash
pip install -r requirements.txt   # Install deps
python main.py                    # Run bot
pytest                            # Run tests
```

## Environment Variables

Copy `config/.env.example` to `config/.env`:
- `TELEGRAM_BOT_TOKEN` — From @BotFather
- `ANTHROPIC_API_KEY` — Claude API key
- `USER_TELEGRAM_ID` — Only respond to this user
- `THINK_OS_PATH` — Path to Think OS directory

## Think OS Access Controls

See `agent/tools.py` for allowed paths. Agent can only:
- READ: `now.md`, `memory/Dian.md`, `memory/timeline/perspective.md`, `memory/timeline/daily/*.md`, `memory/timeline/todo/*.md`, `memory/people/*.md`
- WRITE: `memory/timeline/daily/*.md`, `memory/timeline/todo/*.md`

## Rules

Detailed conventions in `.claude/rules/`:
- `code-style.md` — Python formatting
- `agent-tools.md` — Tool design patterns
- `testing.md` — pytest conventions
