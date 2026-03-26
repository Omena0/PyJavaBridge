---
title: ClientMod [ext]
subtitle: Client capability bridge for commands, scripts, and custom data
---

# ClientMod [ext]

`ClientMod` is a PyJavaBridge extension for communicating with a supported client mod over a custom packet channel.

```python
from bridge.extensions.client_mod import (
    is_available,
    send_command,
    send_data,
    register_script,
    set_permissions,
    get_permissions,
    register_request_data,
    unregister_request_data,
    on_client_data,
    on_permission_change,
)
```

---

## Overview

The extension provides:

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

### Availability

```python
await is_available(player) -> bool
```

### Commands

```python
await send_command(player, capability, args=None, handle=None, timeout_ms=1000)
```

### Data

```python
await send_data(player, channel, payload=None, timeout_ms=1000)
```

### Scripts

```python
await register_script(player, name, source, auto_start=True, metadata=None, timeout_ms=2000)
```

### Permissions

```python
await set_permissions(player, capabilities, reason=None, remember_prompt=True, timeout_ms=3000)
await get_permissions(player)
```

### request() Data Keys

```python
await register_request_data(key, value)
await unregister_request_data(key)
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
- network.custom.send

## Events

Use decorators to receive pushed events from client-mod packets:

- on_client_data
- on_permission_change

Example:

```py
@on_client_data
async def handle_client_data(event):
    data = event.data
    print("client data", data)
```

## Notes

- Permission checks are enforced by the client mod.
- Capability names should match the modular path convention used by capability modules.
- Binary protocol framing is big-endian.
