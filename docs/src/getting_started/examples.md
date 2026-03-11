---
title: Examples
subtitle: Complete script examples
---

# Examples

Full working scripts that demonstrate PyJavaBridge features. Each example is a standalone script you can drop into your `plugins/PyJavaBridge/scripts/` folder.

| Example | Description | Concepts |
| ------- | ----------- | -------- |
| [Commands & GUI](examples_command.html) | Commands, raycast teleport, inventory GUIs, click events | `@command`, `@event`, `Inventory`, `raycast`, `Player` |
| [Spawn Protection](examples_spawn_protect.html) | Prevent building near spawn with block events | `@event`, `event.cancel()`, block coordinates |
| [Temporary Ban](examples_tempban.html) | Ban system with durations, persistence, and login enforcement | `@command`, `@event`, `Player`, state management |
| [Dungeon Generator](examples_dungeon.html) | Procedural dungeon with rooms, loot, mobs, and lifecycle | `Dungeon`, `ItemBuilder`, `@command`, extension events |

---

## Tips for Writing Scripts

1. **Always import from bridge:** `from bridge import *`
2. **Use async/await:** Most bridge methods return awaitables
3. **Name your event handlers after the event:** `async def block_break(event)` handles `block_break` events
4. **Commands auto-register:** The function name becomes the command name
5. **Cancel events to prevent default behavior:** `event.cancel()`
6. **Use the [`Config`](config.html) class for persistence** instead of global dictionaries
