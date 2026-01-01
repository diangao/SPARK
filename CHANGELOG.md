# Changelog

## 2025-12-22 - Production Deployment

### Deployed
- VPS on DigitalOcean ($4/month, Ubuntu 24.04, SFO3)
- Docker containerized deployment
- Think OS sync via deploy key
- Timezone set to America/Los_Angeles

### Added
- `Dockerfile` - Container image
- `docker-compose.yml` - One-command deployment
- `deploy/` - Deployment scripts and docs
- `.dockerignore` - Optimized builds
- `.claude/rules/deployment.md` - Deployment knowledge base

### Fixed
- **Glob matching**: `fnmatch` → `PurePath.match()` for `**` support
  - `tinker/**/*.md` now correctly matches nested paths
- **Message collision**: Added `_user_interacting` flag
  - Orchestrator skips sending when coach is responding
- **Stale state**: Orchestrator now force-reloads state from disk
  - Prevents guilt trips after user already responded

## 2025-12-21 - Orchestrator v2

### Changed
- Switched orchestrator from Haiku to Sonnet (follows instructions better)
- Escalation rules as PRIORITY #1
- Test mode: 15 sec tick, Production: 15 min tick

### Added
- MAXIMUM GUILT MODE (10+ unanswered): Loads profile/perspective as ammunition
- Daily history auto-reset at midnight
- Context-aware openers using daily file content

### Fixed
- State persistence path (was saving to project dir, not Think OS)
- Message splitting (newlines only, model controls format)

## 2025-12-20 - Phase 1 Complete

### Added
- Telegram bot with Claude agent
- Think OS read/write integration
- APScheduler for proactive messaging
- Guilt trip personality from protocol.md
- Learning system (learned.md)
