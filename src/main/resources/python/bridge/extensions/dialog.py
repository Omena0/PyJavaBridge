"""Dialog system — branching player conversations."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional, Tuple, Union

import bridge


class DialogEntry:
    """A single step in a dialog sequence.

    Args:
        speaker: Name shown as the speaker.
        text: Message text.
        answers: Optional list of ``(answer_text, next)`` where *next* is
                 another :class:`DialogEntry` or a callback ``(player) -> ...``.
        delay: Auto-advance after this many seconds if no answers, or timeout
               if answers are present but the player doesn't respond.
    """

    def __init__(
        self,
        speaker: str,
        text: str,
        answers: Optional[List[Tuple[str, Union[DialogEntry, Callable[..., Any]]]]] = None,
        delay: Optional[float] = None,
    ):
        self.speaker = speaker
        self.text = text
        self.answers = answers or []
        self.delay = delay

class Dialog:
    """A full dialog sequence that can be played for a player.

    Build the dialog as a chain of :class:`DialogEntry` nodes, then call
    ``start(player)`` to begin.

    Example::

        intro = DialogEntry("Bob", "Hello there!", [
            ("Hi!", DialogEntry("Bob", "Welcome!")),
            ("Go away", lambda p: p.send_message("Fine...")),
        ])
        dialog = Dialog(intro)
        dialog.start(player)
    """

    def __init__(self, root: DialogEntry):
        self._root = root
        self._active: dict[str, bool] = {}  # player uuid -> active

    def start(self, player: Any):
        puuid = str(player.uuid)
        self._active[puuid] = True
        asyncio.ensure_future(self._play(player, self._root))

    def stop(self, player: Any):
        puuid = str(player.uuid)
        self._active.pop(puuid, None)

    def is_active(self, player: Any) -> bool:
        return self._active.get(str(player.uuid), False)

    async def _play(self, player: Any, entry: DialogEntry):
        from bridge import server
        puuid = str(player.uuid)
        if not self._active.get(puuid):
            return

        # Show the dialog text
        msg = f"<{entry.speaker}> {entry.text}"
        await player.send_message(msg)

        if entry.answers:
            # Show answer options
            for i, (answer_text, _) in enumerate(entry.answers):
                await player.send_message(f"  [{i + 1}] {answer_text}")

            # Wait for player chat response
            chosen = await self._wait_for_answer(player, len(entry.answers), entry.delay)
            if chosen is None:
                # Timeout or stopped
                self._active.pop(puuid, None)
                return

            _, next_step = entry.answers[chosen]
            if isinstance(next_step, DialogEntry):
                await self._play(player, next_step)
            elif callable(next_step):
                result = next_step(player)
                if asyncio.iscoroutine(result):
                    await result
        else:
            # No answers — auto-advance or end
            if entry.delay is not None:
                try:
                    await server.after(int(entry.delay * 20))
                except Exception:
                    pass

        if not entry.answers:
            self._active.pop(puuid, None)

    async def _wait_for_answer(self, player: Any, count: int,
                                timeout_sec: Optional[float]) -> Optional[int]:
        """Wait for the player to type a number 1..count in chat."""
        puuid = str(player.uuid)
        future: asyncio.Future[int] = asyncio.get_event_loop().create_future()

        async def _chat_handler(event: Any):
            ep = event.fields.get("player")
            if ep is None:
                return
            ep_uuid = ep.fields.get("uuid") if hasattr(ep, "fields") else None
            if ep_uuid != puuid:
                return
            raw = event.fields.get("message", "").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < count:
                    if not future.done():
                        future.set_result(idx)
                    event.cancel()

        bridge._connection.on("player_chat", _chat_handler)
        bridge._connection.subscribe("player_chat", False)

        try:
            if timeout_sec is not None:
                return await asyncio.wait_for(future, timeout=timeout_sec)
            else:
                return await future
        except asyncio.TimeoutError:
            return None
        finally:
            # Remove the handler
            handlers = bridge._connection._handlers.get("player_chat", [])
            if _chat_handler in handlers:
                handlers.remove(_chat_handler)
