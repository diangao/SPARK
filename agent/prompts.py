"""Command prompts - Think OS session commands migrated from Claude Code."""

COMMANDS = {
    "startup": """Think OS session startup.

1. **Read core context** (use your preloaded context, no need to read again):
   - User profile — preferences and patterns
   - now.md — active topics
   - recent daily file — what happened lately

2. **Output a brief summary**:
   - What are today's priorities based on now.md and recent activity?
   - Any open threads to continue?
   - What's the current focus/mood?

3. **Ask**: "What would you like to focus on today?"

Keep it concise. 3-5 bullet points max for the summary.
""",

    "midcheck": """Think OS mid-session check.

1. **Check current state**:
   - What was the focus set earlier today?
   - Read today's daily file if exists

2. **Ask**:
   - "How's it going? Any progress on [focus]?"
   - "Anything blocking you?"

3. **Based on response**, offer to:
   - Log progress to daily file
   - Adjust focus if needed
   - Suggest a break if been working long

Keep it casual and brief.
""",

    "wrapup": """Think OS session wrapup.

1. **Review today**:
   - Read today's daily file
   - What was accomplished?
   - What's still open?

2. **Prompt reflection**:
   - "What went well today?"
   - "Anything to carry over to tomorrow?"

3. **Write to daily file**:
   - Add wrapup section with summary
   - Note any insights or learnings

4. **Look ahead**:
   - "Any thoughts on tomorrow's focus?"

Keep the wrapup concise but meaningful.
""",

    "focus": """Help set today's focus.

1. **Check context**:
   - What's in now.md (active topics)?
   - What's in work.md (current tasks)?
   - What did I do yesterday?

2. **Ask**:
   - "What's the ONE thing you want to focus on today?"

3. **Once decided**:
   - Write focus to today's daily file
   - Offer a concrete first step

Keep it actionable. One focus, one next step.
""",

    "schedule": """Help plan today's schedule.

Use the following format to write the schedule to today's daily file:

## Schedule

- [ ] 09:00 - 10:30 | Task description
- [ ] 10:30 - 10:45 | Break
- [ ] 10:45 - 12:00 | Task description
...

## Check-ins


1. **Check current time** (use get_current_time)
2. **Ask what user wants to accomplish today**
3. **Create a realistic schedule** with:
   - Deep work blocks (90-120 min)
   - Breaks between blocks (15 min)
   - Lunch break
   - Buffer time for unexpected things
4. **Write to today's daily file** (memory/timeline/daily/YYYY-MM-DD.md)
5. **Confirm the plan** and ask if any adjustments needed

Tips:
- Be realistic about time
- Include breaks
- Front-load important work
- Leave afternoon for meetings/admin
""",

    "checkin": """Quick check-in on current progress.

1. **Get current time and today's schedule**
2. **Ask**: "How's it going? Any blockers?"
3. **Based on response**:
   - If done → Mark block as complete, celebrate briefly
   - If stuck → Offer specific help
   - If need more time → Suggest adjusting schedule
4. **Log the check-in** to today's daily file under ## Check-ins:
   - HH:MM | What they said (brief)
5. **Look ahead**: What's next on the schedule?

Keep it brief and supportive.
""",
}


def get_command(name: str) -> str | None:
    """Get a command prompt by name."""
    return COMMANDS.get(name.lower())


def list_commands() -> list[str]:
    """List all available commands."""
    return list(COMMANDS.keys())
