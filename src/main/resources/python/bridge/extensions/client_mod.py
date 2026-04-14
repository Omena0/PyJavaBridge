"""Client mod extension — high-level client capability bridge. [ext]"""
from __future__ import annotations

import asyncio as _asyncio
import base64 as _base64
import shutil as _shutil
import sys as _sys
from types import SimpleNamespace as _SimpleNamespace
from typing import Any as _Any, AsyncIterable as _AsyncIterable, Callable as _Callable, Iterable as _Iterable, cast as _cast

from bridge.connection import BridgeConnection as _BridgeConnection
from bridge.types import BridgeCall as _BridgeCall, async_task as _async_task

_connection: _BridgeConnection = None  # type: ignore[assignment]

_client_data_subscribed = False
_client_permission_subscribed = False

def _ensure_data_subscription() -> None:
    """Ensure data subscription."""
    global _client_data_subscribed
    if _client_data_subscribed or _connection is None:
        return
    _connection.subscribe("client_mod_data", False)
    _client_data_subscribed = True

def _ensure_permission_subscription() -> None:
    """Ensure permission subscription."""
    global _client_permission_subscribed
    if _client_permission_subscribed or _connection is None:
        return
    _connection.subscribe("client_mod_permission", False)
    _client_permission_subscribed = True

def _has_msgpack() -> bool:
    """Has msgpack."""
    try:
        import msgpack  # type: ignore[import-not-found]
        return True
    except Exception:
        return False

class ClientModSession:
    """High-level client_mod interface scoped to a single player."""

    __slots__ = ("player",)

    def __init__(self, player: _Any) -> None:
        """Initialize the instance."""
        self.player = player

    @_async_task
    async def is_available(self) -> bool:
        """Is available."""
        value = await _connection.call(target="client_mod", method="isAvailable", args=[self.player])
        return bool(value)

    @_async_task
    async def command(self, capability: str, args: dict[str, _Any] | None = None,
            handle: str | None = None, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Command."""
        result = await _connection.call(
            target="client_mod",
            method="sendCommand",
            args=[self.player, capability, args or {}, handle, int(timeout_ms)],
        )
        return result if isinstance(result, dict) else {"status": "ok", "result": result}

    @_async_task
    async def data(self, channel: str, payload: dict[str, _Any] | None = None,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Data."""
        result = await _connection.call(
            target="client_mod",
            method="sendData",
            args=[self.player, channel, payload or {}, int(timeout_ms)],
        )
        return result if isinstance(result, dict) else {"status": "ok", "result": result}

    @_async_task
    async def register_script(self, name: str, source: str, auto_start: bool = True,
            metadata: dict[str, _Any] | None = None, timeout_ms: int = 2000) -> dict[str, _Any]:
        """Register script."""
        result = await _connection.call(
            target="client_mod",
            method="registerScript",
            args=[self.player, name, source, bool(auto_start), metadata or {}, int(timeout_ms)],
        )
        return result if isinstance(result, dict) else {"status": "ok", "result": result}

    @_async_task
    async def set_permissions(self, capabilities: list[str], reason: str | None = None,
            remember_prompt: bool = True, timeout_ms: int = 60_000) -> dict[str, _Any]:
        """Set permissions."""
        result = await _connection.call(
            target="client_mod",
            method="setPermissions",
            args=[self.player, capabilities, reason or "", bool(remember_prompt), int(timeout_ms)],
        )
        return result if isinstance(result, dict) else {"status": "ok", "result": result}

    @_async_task
    async def get_permissions(self) -> list[str]:
        """Get permissions."""
        result = await _connection.call(target="client_mod", method="getPermissions", args=[self.player])
        if isinstance(result, list):
            return [str(value) for value in result]
        return []

    @_async_task
    async def raycast(self, max_distance: float = 64.0, include_fluids: bool = False,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Raycast."""
        args = {"max_distance": float(max_distance), "include_fluids": bool(include_fluids)}
        return await self.command("raycast.cast", args, timeout_ms=int(timeout_ms))

    @_async_task
    async def entities_list(self, query: dict[str, _Any] | None = None,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Entities list."""
        return await self.command("entities.list", query or {}, timeout_ms=int(timeout_ms))

    @_async_task
    async def entities_query(self, query: dict[str, _Any] | None = None,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Entities query."""
        return await self.command("entities.query", query or {}, timeout_ms=int(timeout_ms))

    @_async_task
    async def particles_spawn(self, particle: str = "minecraft:smoke", x: float | None = None,
            y: float | None = None, z: float | None = None, vx: float = 0.0, vy: float = 0.0,
            vz: float = 0.0, count: int = 1, spread: float = 0.0, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Particles spawn."""
        args: dict[str, _Any] = {
            "particle": particle,
            "vx": float(vx),
            "vy": float(vy),
            "vz": float(vz),
            "count": int(count),
            "spread": float(spread),
        }
        if x is not None:
            args["x"] = float(x)
        if y is not None:
            args["y"] = float(y)
        if z is not None:
            args["z"] = float(z)
        return await self.command("particles.spawn", args, timeout_ms=int(timeout_ms))

    @_async_task
    async def metrics_get(self, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Metrics get."""
        return await self.command("metrics.get", {}, timeout_ms=int(timeout_ms))

    @_async_task
    async def stream_audio_file(self, path: str, stream_id: str | None = None,
            sample_rate: int = 48000, channels: int = 2, chunk_size: int = 4096,
            stop_when_done: bool = True) -> dict[str, _Any]:
        """Stream audio file."""
        args: dict[str, _Any] = {"sample_rate": int(sample_rate), "channels": int(channels)}
        if stream_id is not None:
            args["stream_id"] = stream_id

        res = await self.command("audio.stream.start", args)
        if res.get("status") != "ok":
            return res
        sid = res.get("stream_id") or stream_id or ""

        use_msgpack = _has_msgpack()
        if _shutil.which("ffmpeg") is None and not path.lower().endswith(".wav"):
            return {"status": "fail", "message": "ffmpeg not available to decode file", "code": "NO_FFMPEG"}

        cmd = ["ffmpeg", "-i", path, "-f", "s16le", "-acodec", "pcm_s16le",
               "-ac", str(channels), "-ar", str(sample_rate), "-hide_banner", "-loglevel", "error", "-"]

        proc = await _asyncio.create_subprocess_exec(*cmd, stdout=_asyncio.subprocess.PIPE, stderr=_asyncio.subprocess.PIPE)
        if proc.stdout is None:
            return {"status": "fail", "message": "Failed to open ffmpeg stdout", "code": "FFMPEG_START_FAILED"}

        try:
            while True:
                chunk = await proc.stdout.read(chunk_size)
                if not chunk:
                    break
                if use_msgpack:
                    await self.data("audio_stream_chunk", {"stream_id": sid, "data": chunk})
                else:
                    await self.data("audio_stream_chunk", {
                        "stream_id": sid,
                        "data_b64": _base64.b64encode(chunk).decode("ascii"),
                    })
            await proc.wait()
        finally:
            if stop_when_done:
                await self.command("audio.stream.stop", {"stream_id": sid})

        return {"status": "ok", "stream_id": sid}

    @_async_task
    async def stream_audio_generator(self,
            gen: _Callable[[], _AsyncIterable[bytes] | _Iterable[bytes]] | _AsyncIterable[bytes] | _Iterable[bytes],
            stream_id: str | None = None, sample_rate: int = 48000, channels: int = 2,
            chunk_size: int = 4096, stop_when_done: bool = True) -> dict[str, _Any]:
        """Stream audio generator."""
        args: dict[str, _Any] = {"sample_rate": int(sample_rate), "channels": int(channels)}
        if stream_id is not None:
            args["stream_id"] = stream_id

        res = await self.command("audio.stream.start", args)
        if res.get("status") != "ok":
            return res
        sid = res.get("stream_id") or stream_id or ""
        use_msgpack = _has_msgpack()

        produced = gen() if callable(gen) else gen
        if hasattr(produced, "__aiter__"):
            async_iter = _cast(_AsyncIterable[bytes], produced)
            async for chunk in async_iter:
                if not chunk:
                    continue
                if use_msgpack:
                    await self.data("audio_stream_chunk", {"stream_id": sid, "data": chunk})
                else:
                    await self.data("audio_stream_chunk", {
                        "stream_id": sid,
                        "data_b64": _base64.b64encode(chunk).decode("ascii"),
                    })
        else:
            loop = _asyncio.get_event_loop()
            sentinel = object()
            q: "_asyncio.Queue[bytes | object]" = _asyncio.Queue(maxsize=16)
            sync_iter = _cast(_Iterable[bytes], produced)

            def producer() -> None:
                """Producer."""
                try:
                    for chunk in sync_iter:
                        if not chunk:
                            continue
                        fut = _asyncio.run_coroutine_threadsafe(q.put(chunk), loop)
                        fut.result(timeout=10.0)
                except Exception:
                    pass
                finally:
                    try:
                        _asyncio.run_coroutine_threadsafe(q.put(sentinel), loop).result(timeout=2.0)
                    except Exception:
                        pass

            fut = loop.run_in_executor(None, producer)
            try:
                while True:
                    chunk = await _asyncio.wait_for(q.get(), timeout=10.0)
                    if chunk is sentinel:
                        break
                    if not isinstance(chunk, (bytes, bytearray)):
                        continue
                    if use_msgpack:
                        await self.data("audio_stream_chunk", {"stream_id": sid, "data": chunk})
                    else:
                        await self.data("audio_stream_chunk", {
                            "stream_id": sid,
                            "data_b64": _base64.b64encode(chunk).decode("ascii"),
                        })
            except _asyncio.TimeoutError:
                pass
            finally:
                try:
                    await _asyncio.wait_for(fut, timeout=2.0)
                except (Exception, _asyncio.TimeoutError):
                    pass

        if stop_when_done:
            await self.command("audio.stream.stop", {"stream_id": sid})

        return {"status": "ok", "stream_id": sid}

    @_async_task
    async def mic_set_mute(self, muted: bool = True, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Mic set mute."""
        return await self.command("microphone.set_mute", {"muted": bool(muted)}, timeout_ms=int(timeout_ms))

    @_async_task
    async def mic_get_state(self, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Mic get state."""
        return await self.command("microphone.get_state", {}, timeout_ms=int(timeout_ms))

    @_async_task
    async def mic_level_subscribe(self, stream_id: str, interval_ms: int = 250,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Mic level subscribe."""
        return await self.command(
            "microphone.level.subscribe",
            {"stream_id": stream_id, "interval_ms": int(interval_ms)},
            timeout_ms=int(timeout_ms),
        )

    @_async_task
    async def mic_level_unsubscribe(self, stream_id: str, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Mic level unsubscribe."""
        return await self.command("microphone.level.unsubscribe", {"stream_id": stream_id}, timeout_ms=int(timeout_ms))

    @_async_task
    async def mic_vad_set(self, enabled: bool, threshold: float = 0.02,
            min_speech_ms: int = 200, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Mic vad set."""
        return await self.command(
            "microphone.vad.set",
            {"enabled": bool(enabled), "threshold": float(threshold), "min_speech_ms": int(min_speech_ms)},
            timeout_ms=int(timeout_ms),
        )

    @_async_task
    async def audio_stream_set_volume(self, stream_id: str, volume: float = 1.0,
            timeout_ms: int = 1000) -> dict[str, _Any]:
        """Audio stream set volume."""
        return await self.command(
            "audio.stream.set_volume",
            {"stream_id": stream_id, "volume": float(volume)},
            timeout_ms=int(timeout_ms),
        )

    @_async_task
    async def audio_stream_pause(self, stream_id: str, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Audio stream pause."""
        return await self.command("audio.stream.pause", {"stream_id": stream_id}, timeout_ms=int(timeout_ms))

    @_async_task
    async def audio_stream_resume(self, stream_id: str, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Audio stream resume."""
        return await self.command("audio.stream.resume", {"stream_id": stream_id}, timeout_ms=int(timeout_ms))

    @_async_task
    async def voice_subscribe(self, stream_id: str, source_player: str | None = None,
            mix: bool = False, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Voice subscribe."""
        args = {"stream_id": stream_id, "source_player": source_player or "", "mix": bool(mix)}
        return await self.command("voice.subscribe", args, timeout_ms=int(timeout_ms))

    @_async_task
    async def voice_unsubscribe(self, stream_id: str, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Voice unsubscribe."""
        return await self.command("voice.unsubscribe", {"stream_id": stream_id}, timeout_ms=int(timeout_ms))

    @_async_task
    async def ui_prompt_confirm(self, title: str | None = None, message: str | None = None,
            remember_option: bool = False, timeout_ms: int = 60000) -> dict[str, _Any]:
        """Ui prompt confirm."""
        args = {
            "title": title or "",
            "message": message or "",
            "remember_option": bool(remember_option),
            "timeout_ms": int(timeout_ms),
        }
        return await self.command("ui.prompt.confirm", args, timeout_ms=int(timeout_ms))

    @_async_task
    async def client_pref_set(self, key: str, value: _Any, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Client pref set."""
        return await self.command("client.pref.set", {"key": key, "value": value}, timeout_ms=int(timeout_ms))

    @_async_task
    async def client_pref_get(self, key: str, timeout_ms: int = 1000) -> dict[str, _Any]:
        """Client pref get."""
        return await self.command("client.pref.get", {"key": key}, timeout_ms=int(timeout_ms))

class ClientMod:
    """High-level client_mod entrypoint.

    Use `client_mod.session(player)` to obtain a per-player API object.
    """

    __slots__ = ()

    def session(self, player: _Any) -> ClientModSession:
        """Session."""
        return ClientModSession(player)

    def for_player(self, player: _Any) -> ClientModSession:
        """For player."""
        return ClientModSession(player)

    def player(self, player: _Any) -> ClientModSession:
        """Player."""
        return ClientModSession(player)

    @_async_task
    async def register_request_data(self, key: str, value: _Any) -> bool:
        """Register request data."""
        result = await _connection.call(target="client_mod", method="registerRequestData", args=[key, value])
        return bool(result)

    @_async_task
    async def unregister_request_data(self, key: str) -> bool:
        """Unregister request data."""
        result = await _connection.call(target="client_mod", method="unregisterRequestData", args=[key])
        return bool(result)

    def on_client_data(self, handler: _Callable[[_Any], _Any]) -> _Callable[[_Any], _Any]:
        """On client data."""
        _ensure_data_subscription()

        def _wrapper(payload: _Any) -> _Any:
            """Wrapper."""
            try:
                parsed = payload
                if hasattr(payload, "fields"):
                    parsed = payload.fields

                if isinstance(parsed, dict):
                    inner = parsed.get("data", parsed)
                    channel = None
                    data_obj = None
                    if isinstance(inner, dict):
                        if "channel" in inner and "payload" in inner:
                            channel = inner.get("channel")
                            data_obj = inner.get("payload")
                        elif "event" in inner and isinstance(inner.get("data"), dict):
                            nested = inner.get("data")
                            if isinstance(nested, dict):
                                channel = nested.get("channel")
                                data_obj = nested.get("payload")
                        else:
                            data_obj = inner
                    else:
                        data_obj = inner

                    evt = _SimpleNamespace(data=data_obj, channel=channel, raw=payload)
                    return handler(evt)
            except Exception:
                pass

            return handler(payload)

        _connection.on("client_mod_data", _wrapper)
        return handler

    def on_permission_change(self, handler: _Callable[[_Any], _Any]) -> _Callable[[_Any], _Any]:
        """On permission change."""
        _ensure_permission_subscription()
        _connection.on("client_mod_permission", handler)
        return handler

client_mod = ClientMod()
