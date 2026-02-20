---
title: PyJavaBridge
subtitle: Expose Bukkit APIs to Python scripts via easy-to-use wrappers
---

# PyJavaBridge

PyJavaBridge is a Minecraft server plugin that lets you write **Python scripts** that interact with the Bukkit/Spigot/Paper API through a high-level async bridge. Every API call is asynchronous under the hood — you write clean `async`/`await` Python and the bridge handles the Java ↔ Python communication transparently.

## Quick Start

```python
from bridge import *

@command("Say hello")
async def hello(event: Event):
    await event.player.send_message("Hello from Python!")
```

Drop your `.py` file into the server's `scripts/` folder and reload. The bridge discovers your `@command` and `@event` handlers automatically.

## Key Features

- **Full Bukkit API** — Players, worlds, blocks, entities, inventories, scoreboards, boss bars, advancements, and more.
- **Async by default** — All Java calls are awaitable. Use `async`/`await` naturally.
- **Decorator-driven** — Register commands, events, and repeating tasks with simple decorators.
- **Helper classes** — `ItemBuilder`, `Sidebar`, `Hologram`, `Menu`, `Cooldown`, `Config`, and display entities for common patterns.
- **Region utilities** — Fill, replace, and shape operations on the world (spheres, cylinders, lines).
- **Particle shapes** — Draw particle lines, spheres, cubes, and rings with one call.
- **Permission integration** — LuckPerms-aware permission and group management.
- **Tab list control** — Full control over player tab list headers, footers, and display names.

## Pages

### Decorators & Core

| Page | Description |
|------|-------------|
| [Decorators](decorators.md) | `@event`, `@command`, `@task` |
| [Exceptions](exceptions.md) | `BridgeError`, `EntityGoneException` |
| [EnumValue](enumvalue.md) | Base class for all enum types |
| [Event](event.md) | Event proxy and event types |

### Server & Entities

| Page | Description |
|------|-------------|
| [Server](server.md) | Global server API |
| [Entity](entity.md) | Base entity proxy |
| [Player](player.md) | Player API (extends Entity) |

### World & Space

| Page | Description |
|------|-------------|
| [World](world.md) | World API, region utilities, particle shapes, spawn helpers |
| [Location](location.md) | 3D position with world, yaw, and pitch |
| [Block](block.md) | Block in the world |
| [Chunk](chunk.md) | World chunk loading/unloading |
| [Vector](vector.md) | 3D vector |

### Items & Inventory

| Page | Description |
|------|-------------|
| [Item](item.md) | ItemStack API |
| [ItemBuilder](itembuilder.md) | Fluent item construction |
| [Inventory](inventory.md) | Inventory management |
| [Material](enums.md#material) | Material enum |

### Effects & Attributes

| Page | Description |
|------|-------------|
| [Effect](effect.md) | Potion effects |
| [Potion](potion.md) | Legacy potion API |
| [Attribute](attribute.md) | Entity attributes |

### Scoreboards & UI

| Page | Description |
|------|-------------|
| [BossBar](bossbar.md) | Boss bar API |
| [Scoreboard](scoreboard.md) | Scoreboard API |
| [Team](team.md) | Team API |
| [Objective](objective.md) | Objective API |
| [Sidebar](sidebar.md) | Sidebar helper |
| [Advancement](advancement.md) | Advancement API |

### Helpers

| Page | Description |
|------|-------------|
| [Config](config.md) | YAML configuration files |
| [Cooldown](cooldown.md) | Per-player cooldowns |
| [Hologram](hologram.md) | Floating text entities |
| [Menu](menu.md) | Chest GUI builder |
| [ActionBarDisplay](actionbardisplay.md) | Persistent action bar messages |
| [BossBarDisplay](bossbardisplay.md) | Boss bar wrapper with cooldown linking |

### Display Entities

| Page | Description |
|------|-------------|
| [BlockDisplay](blockdisplay.md) | Block display entity |
| [ItemDisplay](itemdisplay.md) | Item display entity |
| [ImageDisplay](imagedisplay.md) | Pixel art display |

### Utilities

| Page | Description |
|------|-------------|
| [Raycast](raycast.md) | Ray tracing in the world |
| [Chat](chat.md) | Chat broadcast helper |
| [Reflect](reflect.md) | Java reflection access |
| [Enums](enums.md) | All enum types |

### Examples

| Page | Description |
|------|-------------|
| [Examples](examples.md) | Full script examples |
