---
title: ClientMod [ext]
subtitle: Client capability bridge for commands, scripts, and custom data
---

# ClientMod [ext]

`ClientMod` is a PyJavaBridge extension for communicating with a supported client mod over a custom packet channel.

The extension exposes a high-level session interface so you do not need to
pass `player` on every call.

```python
from bridge.extensions.client_mod import client_mod

cm = client_mod.session(player)
if await cm.is_available():
    await cm.command("audio.play", {"sound": "block.note_block.bell", "volume": 1.0, "pitch": 1.0})
```

---

## Overview

The interface provides:

- capability command dispatch to client
- script registration on client
- permission requests and grant inspection
- custom data channel
- request() data key registry used by client scripts

All responses are dictionaries that follow the status contract:

- status ok
- status fail with message and optional code

---

## Basic Usage

```python
result = await send_command(
    player,
    "audio.play",
    {
        "sound": "block.note_block.bell",
        "volume": 1.0,
        "pitch": 1.0,
    },
)

if result.get("status") != "ok":
    player.send_message(f"Client command failed: {result.get('message')}")
```

---

## API

### High-level Interface

```python
from bridge.extensions.client_mod import client_mod

cm = client_mod.for_player(player)
await cm.register_script("hud", SOURCE, auto_start=True)
await cm.metrics_get()
await cm.voice_subscribe("party", source_player=None, mix=True)
```

### Availability

```python
await cm.is_available() -> bool
```

### Commands

```python
await cm.command(capability, args=None, handle=None, timeout_ms=1000)
```

### Data

```python
await cm.data(channel, payload=None, timeout_ms=1000)
```

### Scripts

```python
await cm.register_script(name, source, auto_start=True, metadata=None, timeout_ms=2000)
```

### Permissions

```python
await cm.set_permissions(capabilities, reason=None, remember_prompt=True, timeout_ms=3000)
await cm.get_permissions()
```

### Spatial and Metrics Helpers

```python
await cm.raycast(max_distance=64.0, include_fluids=False)
await cm.entities_list({"radius": 32, "type": "zombie"})
await cm.entities_query({"name": "villager", "limit": 5})
await cm.particles_spawn("minecraft:flame", count=16, spread=0.35)
await cm.metrics_get()
```

### request() Data Keys

```python
await client_mod.register_request_data(key, value)
await client_mod.unregister_request_data(key)
```

### Audio Stream Helpers

```python
await cm.stream_audio_file(path, stream_id=None, sample_rate=48000, channels=2, chunk_size=4096)
await cm.stream_audio_generator(gen, stream_id=None, sample_rate=48000, channels=2, chunk_size=4096)
await cm.audio_stream_set_volume(stream_id, volume=1.0)
await cm.audio_stream_pause(stream_id)
await cm.audio_stream_resume(stream_id)
```

`stream_audio_generator` accepts either:

- a callable returning an async iterable or iterable of PCM chunks
- an async iterable directly
- an iterable directly

### Microphone and Voice Helpers

```python
await cm.mic_set_mute(muted=True)
await cm.mic_get_state()
await cm.mic_level_subscribe(stream_id, interval_ms=250)
await cm.mic_level_unsubscribe(stream_id)
await cm.mic_vad_set(enabled=True, threshold=0.02, min_speech_ms=200)

await cm.voice_subscribe(stream_id, source_player=None, mix=False)
await cm.voice_unsubscribe(stream_id)
```

### UI Prompt and Client Preferences

```python
await cm.ui_prompt_confirm(title=None, message=None, remember_option=False, timeout_ms=60000)
await cm.client_pref_set(key, value)
await cm.client_pref_get(key)
```

## Implemented Capabilities

The client supports the following capabilities:

- audio.play
- audio.stop
- draw.2d.line
- draw.2d.rect
- draw.2d.circle
- draw.2d.text
- draw.2d.image
- draw.3d.line
- draw.3d.rect
- draw.3d.ball
- draw.3d.text
- draw.3d.image
- event.frame
- event.tick
- event.keydown
- event.keyup
- event.keybind
- event.network.custom_recv
- keybinds.register
- keybinds.unregister
- raycast.cast
- entities.list
- entities.query
- particles.spawn
- metrics.get
- network.custom.send
- audio.stream.start
- audio.stream.stop

## Audio streaming

The client supports server-driven streaming of raw PCM (signed 16-bit little-endian)
audio. Use the Python-facing extension APIs rather than sending raw JSON frames.

```py
# Start a stream (returns stream_id)
res = await send_command(player, "audio.stream.start", {"stream_id": "mystream", "sample_rate": 48000, "channels": 2})
if res.get("status") != "ok":
    player.send_message("Failed to start audio stream: %s" % res.get("message"))

# Stop the stream
await send_command(player, "audio.stream.stop", {"stream_id": "mystream"})
```

Chunks (binary): send raw PCM bytes using `send_data`. When sending binary chunks the
bridge prefers msgpack (binary-safe); if msgpack is unavailable you can Base64-encode
the data instead. Example (raw PCM file):

```py
with open("audio.pcm", "rb") as f:
    while True:
        chunk = f.read(4096)
        if not chunk:
            break
        # send_data accepts dict payloads; 'data' may be bytes when msgpack is enabled
        await send_data(player, "audio_stream_chunk", {"stream_id": "mystream", "data": chunk})

# or, if you must use JSON-only transport, send Base64:
import base64
with open("audio.pcm", "rb") as f:
    while (chunk := f.read(4096)):
        await send_data(player, "audio_stream_chunk", {"stream_id": "mystream", "data_b64": base64.b64encode(chunk).decode("ascii")})
```

Notes and limitations:

- This implementation plays raw PCM using the JVM audio system (signed 16-bit little-endian).
  OGG/MP3 streaming is not supported yet.
- Streams are simple FIFO queues; the client may drop or block if the producer
  outpaces playback. Use reasonable chunk sizes and an appropriate sample rate.
- Playback occurs on a background thread and does not use Minecraft's sound manager.

## Events

Use decorators to receive pushed events from client-mod packets:

- client_mod.on_client_data
- client_mod.on_permission_change

Example:

```py
@client_mod.on_client_data
async def handle_client_data(event):
    data = event.data
    print("client data", data)
```

## Notes

- Permission checks are enforced by the client mod.
- Capability names should match the modular path convention used by capability modules.
- Binary protocol framing is big-endian.
