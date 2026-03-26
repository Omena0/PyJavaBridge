---
title: Tempban Example
subtitle: Ban system with durations, persistence, and login enforcement
---

# Tempban Example

A full-featured ban command that supports permanent bans, timed bans
with human-readable durations (e.g. `2h30m`), optional reasons, and
automatic enforcement on login.

> **Note:** This example stores bans in memory.  They will be lost on
> server restart.  For production use, swap the `bans` dict for a
> `Config` or database.

Drop this file into `plugins/PyJavaBridge/scripts/` and reload the server.
Requires the `humanfriendly` pip package: `pip install humanfriendly`.

```python
"""Ban users for customizable amounts of time."""

# humanfriendly provides format_timespan() which turns seconds into
# readable strings like "2 hours and 30 minutes".
from humanfriendly import format_timespan
from time import time as time_now
from bridge import *
from typing import Optional
import re

# ─── In-Memory Ban Storage ──────────────────────────────────────────
# Keys are player UUIDs (strings).
# Values are tuples: (expire_timestamp_or_None, reason_string).
# If the timestamp is None, the ban is permanent.
bans = {}


# ─── Duration Parser ───────────────────────────────────────────────
# Converts strings like "2h30m" or "7d" into total seconds.
# Supported units: s (seconds), m (minutes), h (hours), d (days),
# w (weeks), mo (months ≈ 30 days), y (years ≈ 365 days).

def parse_time(time: str) -> int:
    """Parse a human-readable time string (e.g. '2h30m') into seconds."""
    if not time:
        raise ValueError('Time string is required')

    # Map each unit suffix to its value in seconds.
    units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800,
        'mo': 2592000,   # ~30 days
        'y': 31536000,   # ~365 days
    }

    # Regex captures pairs like ("2", "h") or ("30", "m").
    # 'mo' must come before single-char units so it matches first.
    pattern = re.compile(r'(\d+)(mo|[smhdwy])', re.IGNORECASE)
    total = 0
    time_str = time.strip().lower()
    idx = 0

    for match in pattern.finditer(time_str):
        # Make sure there are no gaps between matches (rejects "2x3h").
        if match.start() != idx:
            raise ValueError(f"Invalid time format: {time}")

        value = int(match.group(1))
        unit = match.group(2)

        if unit not in units:
            raise ValueError(f"Unknown time unit: {unit}")

        total += value * units[unit]
        idx = match.end()

    # If we didn't consume the entire string, the format is invalid.
    if idx != len(time_str):
        raise ValueError(f"Invalid time format: {time}")

    return total


# ─── Ban Command ────────────────────────────────────────────────────
# Usage:  /ban <player> [duration] [reason]
# - duration is optional: omit it for a permanent ban.
# - reason is optional: defaults to "Ban hammer has spoken!"
#
# The 't' and 'r' parameter names are short because players type them
# as positional arguments in chat.

@command('Ban someone for a specified time or permanently')
async def ban(event: Event, user: str, t: Optional[str] = None, r: Optional[str] = None):
    """Ban a player for a specified time or permanently."""
    global bans

    # Only server operators can ban players.
    if not event.player.is_op:
        event.player.send_message('No permission!')
        event.player.play_sound('block_note_block_bass')
        return

    # Look up the target player by name.
    target = Player(name=user)

    # Parse the duration (None means permanent).
    duration = parse_time(t) if t else None
    reason = r or "Ban hammer has spoken!"

    # Build the kick message the banned player will see.
    reason_text = (
        f"You have been {'permanently ' if not duration else ''}banned"
        f"{f'\nFor {format_timespan(duration)}' if duration else ''}"
        f"\nReason: {reason}"
    )

    # Kick the player immediately so they see the ban message.
    await target.kick(reason_text)

    # Store the ban: expire timestamp (or None for permanent) + reason.
    bans[target.uuid] = (time_now() + duration if duration else None, reason)

    # Confirm to the operator.
    event.player.send_message(
        f"{user} has been {'permanently ' if not duration else ''}banned "
        f"{f'for {format_timespan(duration)}' if duration else ''}"
    )


# ─── Unban Command ─────────────────────────────────────────────────
# Usage:  /unban <player>
# Removes the player from the ban dict so they can rejoin.

@command('Unban someone')
async def unban(event: Event, user: str):
    """Unban a previously banned player."""
    global bans

    if not event.player.is_op:
        event.player.send_message('No permission!')
        event.player.play_sound(Sound.from_name('BLOCK_NOTE_BLOCK_BASS'))
        return

    target = Player(name=user)

    # Check that the player is actually banned before trying to remove.
    if target.uuid not in bans:
        event.player.send_message("That user is not banned")
        event.player.play_sound(Sound.from_name('BLOCK_NOTE_BLOCK_BASS'))
        return

    # Remove the ban entry.
    bans.pop(target.uuid)

    event.player.send_message(f"{user} has been unbanned.")


# ─── Login Enforcement ─────────────────────────────────────────────
# When a banned player tries to join, we check if their ban has
# expired.  If it has, we silently remove it and let them in.
# If it hasn't, we kick them again with the remaining time.

@event
async def player_join(event: Event):
    """Kick banned players on join if their ban is still active."""
    global bans
    uuid = event.player.uuid

    # Player isn't banned — nothing to do.
    if uuid not in bans:
        return

    time, reason = bans[uuid]

    # For timed bans, compute seconds remaining.
    if time:
        time -= time_now()

    # If the ban has expired, clean it up and let the player join.
    if time and time <= 0:
        bans.pop(uuid)
        return

    # Ban is still active — kick the player with an updated message.
    event.player.kick(
        f"You have been {'permanently ' if not time else ''}banned"
        f"{f'\nFor {format_timespan(time)}' if time else ''}"
        f"\nReason: {reason}"
    )
```
