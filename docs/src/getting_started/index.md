---
title: PyJavaBridge
page_title: QuickStart
og_title: Home
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
| ---- | ----------- |
| [Decorators](decorators.md) | `@event`, `@command`, `@task` |
| [Exceptions](exceptions.md) | `BridgeError`, `EntityGoneException` |
| [EnumValue](enumvalue.md) | Base class for all enum types |
| [Event](event.md) | Event proxy and event types |

### Server & Entities

| Page | Description |
| ---- | ----------- |
| [Server](server.md) | Global server API |
| [Entity](entity.md) | Base entity proxy |
| [Player](player.md) | Player API (extends Entity) |
| [Entity Subtypes](entitysubtypes.md) | ArmorStand, Villager, ItemFrame, FallingBlock, AreaEffectCloud |

### World & Space

| Page | Description |
| ---- | ----------- |
| [World](world.md) | World API, region utilities, particle shapes, spawn helpers |
| [Location](location.md) | 3D position with world, yaw, and pitch |
| [Block](block.md) | Block in the world |
| [BlockSnapshot](blocksnapshot.md) | Capture and restore block regions |
| [Chunk](chunk.md) | World chunk loading/unloading |
| [Vector](vector.md) | 3D vector |

### Items & Inventory

| Page | Description |
| ---- | ----------- |
| [Item](item.md) | ItemStack API |
| [ItemBuilder](itembuilder.md) | Fluent item construction |
| [Inventory](inventory.md) | Inventory management |
| [Recipe](recipe.md) | Custom crafting recipes |
| [Material](enums.md#material) | Material enum |

### Effects & Attributes

| Page | Description |
| ---- | ----------- |
| [Effect](effect.md) | Potion effects |
| [Potion](potion.md) | Legacy potion API |
| [Attribute](attribute.md) | Entity attributes |

### Scoreboards & UI

| Page | Description |
| ---- | ----------- |
| [BossBar](bossbar.md) | Boss bar API |
| [Scoreboard](scoreboard.md) | Scoreboard API |
| [Team](team.md) | Team API |
| [Objective](objective.md) | Objective API |
| [Sidebar](sidebar.md) | Sidebar helper |
| [Advancement](advancement.md) | Advancement API |

### Helpers

| Page | Description |
| ---- | ----------- |
| [Config](config.md) | Configuration files (TOML, JSON, properties) |
| [Cooldown](cooldown.md) | Per-player cooldowns |
| [State](state.md) | Key-value state container |
| [Hologram](hologram.md) | Floating text entities |
| [Menu](menu.md) | Chest GUI builder |
| [Paginator](paginator.md) | Multi-page menu |
| [ActionBarDisplay](actionbardisplay.md) | Persistent action bar messages |
| [BossBarDisplay](bossbardisplay.md) | Boss bar wrapper with cooldown linking |
| [FireworkEffect](firework.md) | Firework builder |
| [TextComponent](textcomponent.md) | Rich text components |
| [BookBuilder](bookbuilder.md) | Written book builder |

### Display Entities

| Page | Description |
| ---- | ----------- |
| [BlockDisplay](blockdisplay.md) | Block display entity |
| [ItemDisplay](itemdisplay.md) | Item display entity |
| [ImageDisplay](imagedisplay.md) | Pixel art display |
| [MeshDisplay](meshdisplay.md) | 3D triangle mesh rendering |

### Utilities

| Page | Description |
| ---- | ----------- |
| [Raycast](raycast.md) | Ray tracing in the world |
| [Chat](chat.md) | Chat broadcast helper |
| [Reflect](reflect.md) | Java reflection access |
| [Enums](enums.md) | All enum types |

### Extensions [ext]

Extensions are imported separately via `from bridge.extensions import ...`.

| Page | Description |
| ---- | ----------- |
| [ImageDisplay](imagedisplay.md) | Pixel art display |
| [MeshDisplay](meshdisplay.md) | 3D triangle mesh rendering |
| [Quest](quest.md) | Quest system with progress tracking |
| [Dialog](dialog.md) | Branching NPC dialog sequences |
| [Bank](bank.md) | Global currency / bank system |
| [Shop](shop.md) | Chest-GUI shop with pagination |
| [TradeWindow](trade.md) | Two-player trade GUI |
| [Ability](ability.md) | Player abilities with cooldowns and mana |
| [ManaStore](mana.md) | Per-player mana tracking |
| [CombatSystem](combat.md) | Combat tagging and logging |
| [LevelSystem](levels.md) | XP and levelling |
| [Region](region.md) | Cuboid region with enter/exit events |
| [Party](party.md) | Temporary player groups |
| [Guild](guild.md) | Persistent guild system |
| [CustomItem](customitem.md) | Custom item registry |
| [Leaderboard](leaderboard.md) | Hologram-based live leaderboard |
| [VisualEffect](visualeffect.md) | Sequenced particle/sound effects |
| [PlayerDataStore](playerdatastore.md) | Persistent per-player key/value storage |
| [Dungeon](dungeon.md) | Instanced dungeon system with WFC generation |
| [NPC](npc.md) | Custom NPC entities |
| [Scheduler](scheduler.md) | Advanced task scheduling |
| [StateMachine](statemachine.md) | Finite state machine |
| [TabList](tablist.md) | Advanced tab list management |
| [Placeholder](placeholder.md) | Placeholder string registry |
| [LootTable](loottable.md) | Loot table generation |
| [ClientMod](clientmod.md) | Client capability bridge with permissions, commands, and data channel |

### Examples

| Page | Description |
| ---- | ----------- |
| [Examples](examples.md) | Full script examples |

### Internals

| Page | Description |
| ---- | ----------- |
| [Bridge](bridge.md) | Overview of the bridge architecture and wire protocol |
| [Events](events_internal.md) | Event subscriptions, dispatch, cancellation, overrides, and commands |
| [Execution](execution.md) | Call dispatch, threading, timing, and batching |
| [Serialization](serialization.md) | Object handles, type serialization, and proxy classes |
| [Lifecycle](lifecycle.md) | Startup, shutdown, and hot reload |
| [Debugging](debugging.md) | Debug logging, metrics, error codes, and performance tips |
