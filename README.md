# S.P.A.R.K.

**System for Proactive Accountability, Rhythm & Knowledge**

It texts you first. It guilt trips you when you ghost it. It won't let you off the hook.

## Why

You know that friend who actually holds you accountable? The one who texts "bruhh" when you said you'd finish something and didn't? The one who won't let you forget?

That's Spark.

Most productivity tools wait politely for you to check them. Spark doesn't. It reads your schedule, knows what you're supposed to be doing, and calls you out when you're slacking.

- **Annoying (in a loving way)** — guilt trips you, sends "hello??", won't stop until you reply
- **Schedule-aware** — knows your time blocks, deadlines, and what you're avoiding
- **Self-learning** — figures out what actually gets you to respond
- **[Think OS](https://github.com/diangao/think-os) native** — integrates with your personal knowledge system

## What It Actually Says

```
spark: how's the MCP research going?
you: [no reply for 20 min]
spark: bruhh
you: [still nothing]
spark: that thing's not gonna build itself
you: [...]
spark: ok fine i'll stop asking
you: OK OK im doing it
spark: finally 🙄
```

## Quick Start

```bash
pip install -r requirements.txt
cp config/.env.example config/.env
# Add your keys to config/.env
python main.py
```

## Telegram Setup

### 1. Create a Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Choose a name (e.g., "My Spark")
4. Choose a username (must end in `bot`, e.g., `my_spark_bot`)
5. Copy the token — this is your `TELEGRAM_BOT_TOKEN`

### 2. Get Your User ID

1. Search for [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send `/start`
3. It replies with your user ID — this is your `USER_TELEGRAM_ID`

### 3. Start Chatting

1. Add your tokens to `config/.env`
2. Run `python main.py`
3. Open your bot in Telegram (search for the username you created)
4. Send `/start`

Now Spark will text you first. Good luck ignoring it.

## Configuration

```bash
# Required
TELEGRAM_BOT_TOKEN=xxx     # From @BotFather
ANTHROPIC_API_KEY=xxx      # Claude API key
USER_TELEGRAM_ID=xxx       # Your Telegram user ID (only this user can use the bot)
THINK_OS_PATH=/path/to/think-os

# Personalization
USER_NAME=your_name        # So Spark knows what to call you
USER_PRONOUNS=they/them    # Or she/her, he/him
GUILT_LEVEL=savage         # chill, medium, or savage
SPARK_STYLE=                # Custom style hint, e.g. "ABC bro who roasts you"

# AI Providers (mix and match for cost vs quality)
ORCHESTRATOR_PROVIDER=deepseek   # deepseek (cheaper) or anthropic
COACH_PROVIDER=anthropic         # anthropic (better) or deepseek
DEEPSEEK_API_KEY=xxx             # Required if using deepseek

# Timing
TICK_MIN_MINUTES=1         # Min minutes between checks (default: 1)
TICK_MAX_MINUTES=20        # Max minutes between checks (default: 20)
QUIET_START=23             # Quiet hours start, 24h format (default: 23 = 11pm)
QUIET_END=8                # Quiet hours end (default: 8 = 8am)

# Development
TEST_MODE=true             # Faster ticks, skips some guards
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  Telegram   │────▶│  Scheduler  │────▶│ Orchestrator │
│             │◀────│ (X-Y min)  │     │  (DeepSeek)  │
└─────────────┘     └─────────────┘     └──────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │    Coach    │────▶│  Think OS   │
                    │  (Sonnet)   │◀────│    (md)     │
                    └─────────────┘     └─────────────┘
```

**Orchestrator**: Checks at random intervals — "should I bother them?" DeepSeek recommended for cost efficiency. Configure timing via:
- `TICK_MIN_MINUTES` — minimum wait between checks (default: 1)
- `TICK_MAX_MINUTES` — maximum wait between checks (default: 20)

**Coach**: Full conversations when you reply. Anthropic Sonnet recommended for quality.

## Think OS Integration

[Think OS](https://github.com/diangao/think-os) is a markdown-based personal operating system — a local folder structure for managing your goals, daily logs, and knowledge. Think of it as a file-based "second brain" that AI agents can read and write to.

Spark uses Think OS to:
- Know what you're supposed to be doing (daily files, schedule)
- Track your goals and hold you to them (perspective, profile)
- Learn what works on you over time (learned.md)
- Remember how many times you've ghosted it (state.json)

### Required Files

```
think-os/memory/
├── spark/
│   ├── protocol.md    # How annoying to be (edit this)
│   ├── learned.md     # What works on you (auto-updated)
│   └── state.json     # How many times you've ghosted
├── profile.md         # Who you are
└── timeline/daily/    # What you're supposed to be doing
```

Want to change Spark's personality? Edit `protocol.md`. No code changes needed.

## Commands

| Command | What it does |
|---------|-------------|
| `/schedule` | Plan your day (so Spark knows what to bug you about) |
| `/checkin` | Admit what you did or didn't do |
| `/startup` | Morning kickoff |
| `/wrapup` | End of day reflection |
| `/focus` | Set one priority |
| `/clear` | Reset (Spark forgets your sins) |

Or just message naturally. Spark adapts.

## Self-Learning

Tell Spark how you want to be bothered:

> "be meaner when i don't reply"

> "less guilt trips pls"

It updates `learned.md` and remembers. Over time, it figures out exactly what gets you moving.

## Deployment (VPS)

### Quick Deploy

```bash
# On fresh Ubuntu VPS
curl -fsSL https://get.docker.com | sh
git clone https://github.com/diangao/S.P.A.R.K..git /opt/spark
cd /opt/spark
cp config/.env.example config/.env
nano config/.env  # Add your keys
docker compose up -d
```

### Think OS Sync

Your [Think OS](https://github.com/diangao/think-os) folder needs to be on the VPS at `/root/think-os`. For private repos, use a deploy key:

```bash
# Generate deploy key on VPS
ssh-keygen -t ed25519 -C "spark-vps" -f ~/.ssh/deploy_key -N ""
cat ~/.ssh/deploy_key.pub  # Add to your Think OS repo as deploy key (with write access)

# Set up SSH config so git uses the deploy key automatically
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

# Clone your Think OS repo
git clone git@github.com:youruser/your-think-os.git /root/think-os
```

**Two-way sync (pull your changes, push Spark's writes):**
```bash
# Set git identity for auto-commits
git config --global user.email "spark-bot@example.com"
git config --global user.name "Spark Bot"

crontab -e
# Add this line (syncs every 5 min):
*/5 * * * * cd /root/think-os && git add -A && git diff --quiet --cached || git commit -m "Spark auto-sync" && git pull --rebase && git push >> /var/log/think-os-sync.log 2>&1
```

### Common Commands

```bash
docker compose logs -f     # View logs
docker compose restart     # Restart
docker compose down        # Stop
git pull && docker compose up -d --build  # Update
```

### Timezone

Set in `docker-compose.yml`:
```yaml
environment:
  - TZ=America/Los_Angeles
```

### API Cost

Spark uses two AI components:
- **Orchestrator**: Checks every few minutes — "should I bother them?"
- **Coach**: Full conversations when you actually reply

You can mix providers to balance cost vs quality:

| Setup | Orchestrator | Coach | Est. Cost/Day |
|-------|--------------|-------|---------------|
| Budget | DeepSeek | DeepSeek | ~$0.10-0.20 |
| Balanced | DeepSeek | Anthropic Sonnet | ~$0.50-1.50 |
| Premium | Anthropic | Anthropic | ~$1-3 |

**Real-world example** (my setup):
- Savage mode, detailed profile.md (~2k tokens context)
- 5-min tick intervals with quiet hours (10pm-8am)
- DeepSeek orchestrator + Sonnet coach
- **~$1.40/day** (~10 RMB)

**Want it cheaper?** Use 15-25 min intervals instead:
```bash
TICK_MIN_MINUTES=15
TICK_MAX_MINUTES=25
```
This cuts orchestrator costs by ~70% → **~$0.35-0.50/day**

Configure providers in `.env`:
```bash
ORCHESTRATOR_PROVIDER=deepseek  # or anthropic
COACH_PROVIDER=anthropic        # recommended for quality
DEEPSEEK_API_KEY=xxx            # if using deepseek
ANTHROPIC_API_KEY=xxx           # if using anthropic
```

### VPS Cost

- DigitalOcean: $4/month (512MB RAM, Ubuntu)
- **Total hosting: ~$5/month** + API costs above

## Contributing

PRs welcome. Most of Spark's personality lives in `protocol.md`, not code — so you can fork it and make your own flavor of annoying.

## License

MIT
