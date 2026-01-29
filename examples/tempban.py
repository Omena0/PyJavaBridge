"""Ban users for customizable amounts of time."""
from humanfriendly import format_timespan
from time import time as time_now
from bridge import *
import re

bans = {}

def parse_time(time:str) -> int:
    if not time:
        raise ValueError('Time string is required')

    units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800,
        'mo': 2592000,
        'y': 31536000,
    }

    pattern = re.compile(r'(\d+)(mo|[smhdwy])', re.IGNORECASE)
    total = 0
    time_str = time.strip().lower()
    idx = 0

    for match in pattern.finditer(time_str):
        if match.start() != idx:
            raise ValueError(f"Invalid time format: {time}")

        value = int(match.group(1))
        unit = match.group(2)

        if unit not in units:
            raise ValueError(f"Unknown time unit: {unit}")

        total += value * units[unit]
        idx = match.end()

    if idx != len(time_str):
        raise ValueError(f"Invalid time format: {time}")

    return total

@command('Ban someone for a specified time or permanently')
async def ban(event: Event, user:str, t:str=None, r:str=None):
    global bans

    if not event.player.is_op():
        event.player.send_message('No permission!')
        event.player.play_sound('block_note_block_bass')
        return

    target = Player(user)
    duration = parse_time(t) if t else None
    reason = r or "Ban hammer has spoken!"

    reason_text = f"You have been {"permanently " if not duration else ""}banned{f"\nFor {format_timespan(duration)}" if duration else ""}\nReason: {reason}"

    await target.kick(reason_text)

    bans[target.uuid] = (time_now() + duration if duration else None, reason)

    event.player.send_message(f"{user} has been {"permanently " if not duration else ""}banned {f"for {format_timespan(duration)}" if duration else ""}")

@command('Unban someone')
async def unban(event: Event, user:str):
    global bans

    if not event.player.is_op():
        event.player.send_message('No permission!')
        event.player.play_sound('block_note_block_bass')
        return

    target = Player(user)

    if not target.uuid in bans:
        event.player.send_message("That user is not banned")
        event.player.play_sound('block_note_block_bass')
        return

    bans.pop(target.uuid)

    event.player.send_message(f"{user} has been unbanned.")

@event
async def player_join(event: Event):
    global bans
    uuid = event.player.uuid

    if uuid not in bans:
        return

    time, reason = bans[uuid]
    if time:
        time -= time_now()

    if time and time <= 0:
        bans.pop(uuid)
        return

    event.player.kick(f"You have been {"permanently " if not time else ""}banned{f"\nFor {format_timespan(time)}" if time else ""}\nReason: {reason}")

